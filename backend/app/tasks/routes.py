from __future__ import annotations

import os

from flask import Blueprint, abort, current_app, g, jsonify, request, send_file

from ..auth.decorators import admin_required, login_required
from ..celery_app import celery
from ..ai.prompts import REQUIRED_GENERATION_TYPES
from ..ai.storage import resolve_local_file_path
from ..models.enums import GeneratedImageType, UserRole
from ..models.generated_image import GeneratedImage
from ..extensions import db
from ..queue import QueueUnavailableError, queue_generation_job
from .serialization import enum_value, serialize_task
from .services import (
    ApiError,
    accept_task,
    assign_task,
    create_task,
    delete_task,
    delete_generated_image,
    ensure_task_generation_access,
    get_task_or_404,
    get_generated_image_or_404,
    list_admin_tasks,
    list_assigned_tasks,
    list_task_audit_logs,
    list_task_generations,
    parse_uuid,
    mark_generated_image_final,
    request_revision,
    set_rls_context,
    start_task,
    submit_task,
)

tasks_bp = Blueprint("tasks", __name__, url_prefix="/api")


def current_user():
    user = getattr(g, "current_user", None)
    if user is None:
        raise ApiError("authentication_required", 401)
    set_rls_context(user)
    return user


def json_payload() -> dict:
    if not request.is_json:
        return {}
    payload = request.get_json(silent=True)
    return payload if isinstance(payload, dict) else {}


def create_task_payload() -> dict:
    uploaded_file = request.files.get("product_image_file")
    if uploaded_file is not None and uploaded_file.filename:
        payload = dict(request.form.items())
        payload["product_image_file"] = uploaded_file
        return payload
    if request.mimetype and request.mimetype.startswith("multipart/form-data"):
        return dict(request.form.items())
    return json_payload()


def _requested_generation_types(payload: dict) -> list[GeneratedImageType]:
    raw_types = payload.get("image_types")
    if raw_types is None:
        raw_type = payload.get("image_type")
        if raw_type is not None:
            raw_types = [raw_type]
    if raw_types is None:
        raw_types = [variant.value for variant in REQUIRED_GENERATION_TYPES]
    if not isinstance(raw_types, list) or not raw_types:
        raise ApiError("image_types_required", 400)

    normalized: list[GeneratedImageType] = []
    seen: set[str] = set()
    for raw_type in raw_types:
        try:
            variant = GeneratedImageType(str(raw_type))
        except ValueError as exc:
            raise ApiError("image_type_invalid", 400) from exc
        if variant.value in seen:
            continue
        seen.add(variant.value)
        normalized.append(variant)
    return normalized


@tasks_bp.errorhandler(ApiError)
def handle_api_error(error: ApiError):
    db.session.rollback()
    current_app.logger.warning("API error on %s: %s (%s)", request.path, error.code, error.message)
    return jsonify({"error": error.code, "message": error.message}), error.status_code


@tasks_bp.route("/local-files/<bucket>/<path:file_path>", methods=["GET"])
def serve_local_storage_file(bucket: str, file_path: str):
    local_fallback_enabled = os.getenv("LOCAL_STORAGE_FALLBACK", "").strip().lower() in {"1", "true", "yes", "on"}
    if not current_app.debug and not local_fallback_enabled:
        abort(404)

    local_path = resolve_local_file_path(bucket=bucket, path=file_path)
    if local_path is None:
        abort(404)
    return send_file(local_path)


@tasks_bp.route("/admin/tasks", methods=["GET"])
@admin_required
def admin_list_tasks():
    current_user()
    return jsonify({"tasks": [serialize_task(task) for task in list_admin_tasks()]})


@tasks_bp.route("/admin/tasks", methods=["POST"])
@admin_required
def admin_create_task():
    try:
        task = create_task(current_user(), create_task_payload())
        return jsonify({"task": serialize_task(task, include_images=True)}), 201
    except ApiError:
        raise
    except Exception as exc:
        current_app.logger.exception("admin_create_task failed")
        raise ApiError("task_create_failed", 500, str(exc)) from exc


@tasks_bp.route("/admin/tasks/<task_id>/assign", methods=["POST"])
@admin_required
def admin_assign_task(task_id: str):
    user = current_user()
    task = get_task_or_404(parse_uuid(task_id, "task_id"))
    assignee_id = parse_uuid(str(json_payload().get("assigned_to") or ""), "assigned_to")
    task = assign_task(user, task, assignee_id)
    return jsonify({"task": serialize_task(task, include_images=True)})


@tasks_bp.route("/admin/tasks/<task_id>/accept", methods=["POST", "PUT"])
@admin_required
def admin_accept_task(task_id: str):
    user = current_user()
    task = get_task_or_404(parse_uuid(task_id, "task_id"))
    task = accept_task(user, task, json_payload())
    return jsonify({"task": serialize_task(task, include_images=True)})


@tasks_bp.route("/admin/tasks/<task_id>/request-revision", methods=["POST", "PUT"])
@admin_required
def admin_request_revision(task_id: str):
    user = current_user()
    task = get_task_or_404(parse_uuid(task_id, "task_id"))
    task = request_revision(user, task, json_payload())
    return jsonify({"task": serialize_task(task, include_images=True)})


@tasks_bp.route("/admin/tasks/<task_id>", methods=["DELETE"])
@admin_required
def admin_delete_task(task_id: str):
    user = current_user()
    task = get_task_or_404(parse_uuid(task_id, "task_id"))
    delete_task(user, task)
    return jsonify({"ok": True})


@tasks_bp.route("/tasks", methods=["GET"])
@login_required
def user_list_tasks():
    user = current_user()
    if user.role == UserRole.ADMIN or enum_value(user.role) == UserRole.ADMIN.value:
        return jsonify({"tasks": [serialize_task(task) for task in list_admin_tasks()]})
    return jsonify({"tasks": [serialize_task(task) for task in list_assigned_tasks(user)]})


@tasks_bp.route("/tasks/<task_id>", methods=["GET"])
@login_required
def user_task_detail(task_id: str):
    user = current_user()
    task = get_task_or_404(parse_uuid(task_id, "task_id"))
    if user.role != UserRole.ADMIN and enum_value(user.role) != UserRole.ADMIN.value and task.assigned_to != user.id:
        raise ApiError("task_not_found", 404)
    return jsonify({"task": serialize_task(task, include_images=True)})


@tasks_bp.route("/tasks/<task_id>/start", methods=["POST", "PUT"])
@login_required
def user_start_task(task_id: str):
    user = current_user()
    task = get_task_or_404(parse_uuid(task_id, "task_id"))
    task = start_task(user, task)
    return jsonify({"task": serialize_task(task, include_images=True)})


@tasks_bp.route("/tasks/<task_id>/submit", methods=["POST", "PUT"])
@login_required
def user_submit_task(task_id: str):
    user = current_user()
    task = get_task_or_404(parse_uuid(task_id, "task_id"))
    task = submit_task(user, task, json_payload())
    return jsonify({"task": serialize_task(task, include_images=True)})


@tasks_bp.route("/my-tasks", methods=["GET"])
@login_required
def user_my_tasks_alias():
    return user_list_tasks()


@tasks_bp.route("/tasks/<task_id>/generations", methods=["POST"])
@login_required
def user_create_generations(task_id: str):
    user = current_user()
    task = get_task_or_404(parse_uuid(task_id, "task_id"))
    payload = json_payload()
    ensure_task_generation_access(user, task)
    if enum_value(task.status) == "accepted":
        raise ApiError("accepted_task_cannot_generate", 409)
    jobs = []
    try:
        for image_type in _requested_generation_types(payload):
            result = queue_generation_job(task_id=str(task.id), actor_user_id=str(user.id), image_type=image_type.value)
            jobs.append({"job_id": result.id, "image_type": image_type.value, "state": "PENDING"})
    except QueueUnavailableError as exc:
        raise ApiError(
            "generation_queue_unavailable",
            503,
            "Image generation queue is unavailable. Start Redis and the Celery worker, then try again.",
        ) from exc
    return jsonify({"jobs": jobs}), 202


@tasks_bp.route("/tasks/<task_id>/generate", methods=["POST"])
@login_required
def user_generate_task_alias(task_id: str):
    return user_create_generations(task_id)


@tasks_bp.route("/generation-jobs/<job_id>", methods=["GET"])
@login_required
def user_generation_job_status(job_id: str):
    _ = current_user()
    try:
        job = celery.AsyncResult(job_id)
        result = job.result
        if job.failed():
            result = {"error": str(job.result)}
        meta = result if isinstance(result, dict) and not job.successful() else None
    except Exception as exc:
        raise ApiError(
            "generation_status_unavailable",
            503,
            "Image generation status is unavailable. Check Redis and the Celery worker.",
        ) from exc
    return jsonify(
        {
            "job_id": job_id,
            "state": job.state,
            "ready": job.ready(),
            "successful": job.successful(),
            "result": result if job.successful() else None,
            "meta": meta,
            "error": str(job.result) if job.failed() else None,
        }
    )


@tasks_bp.route("/jobs/<job_id>/status", methods=["GET"])
@login_required
def user_generation_job_status_alias(job_id: str):
    return user_generation_job_status(job_id)


@tasks_bp.route("/tasks/<task_id>/generations/<generation_id>/mark-final", methods=["POST"])
@login_required
def user_mark_generation_final(task_id: str, generation_id: str):
    user = current_user()
    task = get_task_or_404(parse_uuid(task_id, "task_id"))
    ensure_task_generation_access(user, task)
    image = get_generated_image_or_404(task, parse_uuid(generation_id, "generation_id"))
    image = mark_generated_image_final(actor=user, task=task, image=image)
    return jsonify({"generation_id": str(image.id), "ok": True})


@tasks_bp.route("/tasks/<task_id>/generations/<generation_id>", methods=["DELETE"])
@login_required
def user_delete_generation(task_id: str, generation_id: str):
    user = current_user()
    task = get_task_or_404(parse_uuid(task_id, "task_id"))
    ensure_task_generation_access(user, task)
    image = get_generated_image_or_404(task, parse_uuid(generation_id, "generation_id"))
    delete_generated_image(actor=user, task=task, image=image)
    return jsonify({"ok": True})


@tasks_bp.route("/generations/<generation_id>", methods=["DELETE"])
@login_required
def user_delete_generation_alias(generation_id: str):
    user = current_user()
    image = db.session.get(GeneratedImage, parse_uuid(generation_id, "generation_id"))
    if image is None:
        raise ApiError("generation_not_found", 404)
    task = get_task_or_404(image.task_id)
    ensure_task_generation_access(user, task)
    delete_generated_image(actor=user, task=task, image=image)
    return jsonify({"ok": True})


@tasks_bp.route("/tasks/<task_id>/generations", methods=["GET"])
@login_required
def user_generation_history(task_id: str):
    user = current_user()
    task = get_task_or_404(parse_uuid(task_id, "task_id"))
    return jsonify({"generations": list_task_generations(task, user)})


@tasks_bp.route("/tasks/<task_id>/audit-logs", methods=["GET"])
@login_required
def user_task_audit_logs(task_id: str):
    user = current_user()
    task = get_task_or_404(parse_uuid(task_id, "task_id"))
    logs = list_task_audit_logs(task, user)
    from .serialization import serialize_audit_log

    return jsonify({"audit_logs": [serialize_audit_log(log) for log in logs]})

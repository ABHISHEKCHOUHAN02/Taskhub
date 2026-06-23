from __future__ import annotations

from flask import Blueprint, g, jsonify, request

from ..auth.routes import admin_required, login_required
from ..extensions import db
from ..models.enums import UserRole
from .serialization import enum_value, serialize_task
from .services import (
    ApiError,
    accept_task,
    assign_task,
    create_task,
    delete_task,
    get_task_or_404,
    list_admin_tasks,
    list_assigned_tasks,
    list_task_generations,
    parse_uuid,
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


@tasks_bp.errorhandler(ApiError)
def handle_api_error(error: ApiError):
    db.session.rollback()
    return jsonify({"error": error.code}), error.status_code


@tasks_bp.route("/admin/tasks", methods=["GET"])
@admin_required
def admin_list_tasks():
    current_user()
    return jsonify({"tasks": [serialize_task(task) for task in list_admin_tasks()]})


@tasks_bp.route("/admin/tasks", methods=["POST"])
@admin_required
def admin_create_task():
    task = create_task(current_user(), json_payload())
    return jsonify({"task": serialize_task(task, include_images=True)}), 201


@tasks_bp.route("/admin/tasks/<task_id>/assign", methods=["POST"])
@admin_required
def admin_assign_task(task_id: str):
    user = current_user()
    task = get_task_or_404(parse_uuid(task_id, "task_id"))
    assignee_id = parse_uuid(str(json_payload().get("assigned_to") or ""), "assigned_to")
    task = assign_task(user, task, assignee_id)
    return jsonify({"task": serialize_task(task, include_images=True)})


@tasks_bp.route("/admin/tasks/<task_id>/accept", methods=["POST"])
@admin_required
def admin_accept_task(task_id: str):
    user = current_user()
    task = get_task_or_404(parse_uuid(task_id, "task_id"))
    task = accept_task(user, task, json_payload())
    return jsonify({"task": serialize_task(task, include_images=True)})


@tasks_bp.route("/admin/tasks/<task_id>/request-revision", methods=["POST"])
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


@tasks_bp.route("/tasks/<task_id>/start", methods=["POST"])
@login_required
def user_start_task(task_id: str):
    user = current_user()
    task = get_task_or_404(parse_uuid(task_id, "task_id"))
    task = start_task(user, task)
    return jsonify({"task": serialize_task(task, include_images=True)})


@tasks_bp.route("/tasks/<task_id>/submit", methods=["POST"])
@login_required
def user_submit_task(task_id: str):
    user = current_user()
    task = get_task_or_404(parse_uuid(task_id, "task_id"))
    task = submit_task(user, task, json_payload())
    return jsonify({"task": serialize_task(task, include_images=True)})


@tasks_bp.route("/tasks/<task_id>/generations", methods=["GET"])
@login_required
def user_generation_history(task_id: str):
    user = current_user()
    task = get_task_or_404(parse_uuid(task_id, "task_id"))
    return jsonify({"generations": list_task_generations(task, user)})

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa
from flask import current_app
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from werkzeug.datastructures import FileStorage

from ..extensions import db
from ..ai import REQUIRED_GENERATION_TYPES, delete_storage_object, build_task_source_image_path, upload_storage_object
from ..ai.storage import StorageUploadError
from ..models.audit_log import AuditLog
from ..models.enums import GeneratedImageType, TaskStatus, UserRole
from ..models.generated_image import GeneratedImage
from ..models.task import Task
from ..models.user import User
from .email import (
    build_task_email_context,
    trigger_task_assigned_email,
    trigger_task_review_email,
    trigger_task_submitted_email,
)
from .serialization import enum_value, serialize_generated_image, snapshot_task


class ApiError(Exception):
    def __init__(self, code: str, status_code: int = 400, message: str | None = None):
        self.code = code
        self.status_code = status_code
        self.message = message or code
        super().__init__(self.message)


def _metadata_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


ALLOWED_PRODUCT_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".tif", ".tiff", ".bmp"}
MAX_PRODUCT_IMAGE_BYTES = 10 * 1024 * 1024
PRODUCT_IMAGE_MIME_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
}


def _read_product_image_file(product_image_file: FileStorage) -> tuple[bytes, str, str]:
    if not product_image_file or not product_image_file.filename:
        raise ApiError("product_image_required", 400)

    filename = os.path.basename(product_image_file.filename)
    _, ext = os.path.splitext(filename)
    ext = ext.lower()
    if ext not in ALLOWED_PRODUCT_IMAGE_EXTENSIONS:
        raise ApiError("product_image_type_invalid", 400)

    file_bytes = product_image_file.read()
    if not file_bytes:
        raise ApiError("product_image_required", 400)
    if len(file_bytes) > MAX_PRODUCT_IMAGE_BYTES:
        raise ApiError("product_image_too_large", 400)

    content_type = (product_image_file.mimetype or "").split(";", 1)[0].strip().lower()
    if not content_type or not content_type.startswith("image/"):
        content_type = PRODUCT_IMAGE_MIME_TYPES.get(ext, "")
    if not content_type:
        raise ApiError("product_image_type_invalid", 400)

    return file_bytes, filename, content_type


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_uuid(value: str | None, field: str) -> uuid.UUID:
    if not value:
        raise ApiError(f"{field}_required", 400)
    try:
        return uuid.UUID(str(value))
    except ValueError as exc:
        raise ApiError(f"{field}_invalid", 400) from exc


def parse_datetime(value: str | None, field: str) -> datetime | None:
    if not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ApiError(
            f"{field}_invalid",
            400,
            "Due date must be a valid date and time, or leave the field empty.",
        ) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def set_rls_context(user: User) -> None:
    role = enum_value(user.role)
    db.session.execute(sa.text("select set_config('app.user_id', :user_id, true)"), {"user_id": str(user.id)})
    db.session.execute(sa.text("select set_config('app.user_role', :role, true)"), {"role": role})


def commit_and_restore_context(user: User) -> None:
    db.session.commit()
    set_rls_context(user)


def get_task_or_404(task_id: uuid.UUID) -> Task:
    task = db.session.scalar(
        select(Task)
        .options(
            selectinload(Task.generated_images),
            selectinload(Task.creator),
            selectinload(Task.assignee),
        )
        .where(Task.id == task_id)
    )
    if task is None:
        raise ApiError("task_not_found", 404)
    return task


def get_active_user_or_404(user_id: uuid.UUID) -> User:
    user = db.session.get(User, user_id)
    if user is None or not user.is_active:
        raise ApiError("assignee_not_found", 404)
    return user


def ensure_assigned_user(task: Task, user: User) -> None:
    if task.assigned_to != user.id:
        raise ApiError("task_not_found", 404)


def add_entity_audit_log(
    *,
    actor: User,
    entity_type: str,
    entity_id: uuid.UUID,
    action: str,
    before: dict[str, Any] | None,
    metadata: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    db.session.add(
        AuditLog(
            actor_user_id=actor.id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            before_data=before,
            after_data=after or {},
            metadata_json=metadata or {},
        )
    )


def add_audit_log(
    *,
    actor: User,
    task: Task,
    action: str,
    before: dict[str, Any] | None,
    metadata: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    add_entity_audit_log(
        actor=actor,
        entity_type="task",
        entity_id=task.id,
        action=action,
        before=before,
        metadata=metadata,
        after=snapshot_task(task) if after is None else after,
    )


def is_admin_user(user: User) -> bool:
    return enum_value(user.role) == UserRole.ADMIN.value


def can_manage_task(user: User, task: Task) -> bool:
    return is_admin_user(user) or task.assigned_to == user.id


def ensure_task_generation_access(user: User, task: Task) -> None:
    if not can_manage_task(user, task):
        raise ApiError("task_not_found", 404)


def get_generated_image_or_404(task: Task, generation_id: uuid.UUID) -> GeneratedImage:
    image = db.session.scalar(select(GeneratedImage).where(GeneratedImage.id == generation_id, GeneratedImage.task_id == task.id))
    if image is None:
        raise ApiError("generation_not_found", 404)
    return image


def list_task_audit_logs(task: Task, user: User) -> list[AuditLog]:
    if not is_admin_user(user) and task.assigned_to != user.id:
        raise ApiError("task_not_found", 404)
    return db.session.scalars(
        select(AuditLog)
        .where(AuditLog.entity_type == "task", AuditLog.entity_id == task.id)
        .order_by(AuditLog.created_at.desc())
    ).all()


def create_task(actor: User, payload: dict[str, Any]) -> Task:
    title = str(payload.get("title") or "").strip()
    product_image_url = str(payload.get("product_image_url") or "").strip()
    product_image_file = payload.get("product_image_file")
    if not title:
        raise ApiError("title_required", 400)

    assignee_raw = str(payload.get("assigned_to") or "").strip()
    assignee = get_active_user_or_404(parse_uuid(assignee_raw, "assigned_to")) if assignee_raw else None
    created_at = now_utc()
    task_id = uuid.uuid4()
    storage_metadata: dict[str, Any] = {}
    if isinstance(product_image_file, FileStorage):
        file_bytes, filename, content_type = _read_product_image_file(product_image_file)
        storage_path = build_task_source_image_path(str(task_id), filename)
        bucket = str(payload.get("product_image_bucket") or current_app.config["SUPABASE_STORAGE_BUCKET"])
        try:
            product_image_url = upload_storage_object(
                bucket=bucket,
                path=storage_path,
                data=file_bytes,
                content_type=content_type,
            )
        except StorageUploadError as exc:
            current_app.logger.error("Product image upload failed: %s", exc.message)
            raise ApiError(exc.code, exc.status_code, exc.message) from exc
        storage_metadata = {
            "source_storage_path": storage_path,
            "source_file_name": filename,
            "source_content_type": content_type,
        }
    elif not product_image_url:
        raise ApiError("product_image_required", 400)
    task = Task(
        id=task_id,
        title=title,
        description=str(payload.get("description") or ""),
        status=TaskStatus.ASSIGNED if assignee else TaskStatus.PENDING,
        created_by=actor.id,
        assigned_to=assignee.id if assignee else None,
        product_image_bucket=str(payload.get("product_image_bucket") or current_app.config["SUPABASE_STORAGE_BUCKET"]),
        product_image_url=product_image_url,
        product_image_metadata={**_metadata_dict(payload.get("product_image_metadata")), **storage_metadata},
        due_at=parse_datetime(str(payload.get("due_at") or "").strip() or None, "due_at"),
        assigned_at=created_at if assignee else None,
    )
    db.session.add(task)
    db.session.flush()
    email_context = None
    if assignee:
        email_context = build_task_email_context(
            task_id=str(task.id),
            task_title=task.title,
            assignee_email=assignee.email,
            assignee_name=assignee.full_name,
        )
    add_audit_log(actor=actor, task=task, action="task.created", before=None)
    commit_and_restore_context(actor)
    current_app.logger.info("Created task %s with product image at %s", task.id, task.product_image_url)
    if email_context:
        try:
            trigger_task_assigned_email(email_context)
        except Exception as exc:
            current_app.logger.warning("Assignment email skipped for task %s: %s", task.id, exc)
    return task


def _required_generation_type_values() -> set[str]:
    return {variant.value for variant in REQUIRED_GENERATION_TYPES}


def _generation_history(existing: GeneratedImage | None) -> list[dict[str, Any]]:
    if existing is None:
        return []
    metadata = existing.metadata_json if isinstance(existing.metadata_json, dict) else {}
    history = metadata.get("history") if isinstance(metadata.get("history"), list) else []
    return list(history)


def save_generated_image(
    *,
    actor: User,
    task: Task,
    image_type: GeneratedImageType,
    angle: str | None,
    image_url: str,
    storage_path: str,
    prompt_used: str,
    metadata: dict[str, Any],
    is_final: bool = False,
) -> GeneratedImage:
    existing = db.session.scalar(
        select(GeneratedImage).where(GeneratedImage.task_id == task.id, GeneratedImage.image_type == image_type)
    )
    now = now_utc()
    if existing is None:
        generated_image = GeneratedImage(
            task_id=task.id,
            image_type=image_type,
            angle=angle,
            image_bucket=str(metadata.get("bucket") or current_app.config["SUPABASE_STORAGE_BUCKET"]),
            image_url=image_url,
            prompt_used=prompt_used,
            metadata_json={},
            is_final=is_final,
            created_by=actor.id,
        )
        db.session.add(generated_image)
        db.session.flush()
        generated_image.metadata_json = {
            **metadata,
            "storage_path": storage_path,
            "history": [],
        }
        generated_image.updated_at = now
        add_entity_audit_log(
            actor=actor,
            entity_type="generated_image",
            entity_id=generated_image.id,
            action="generated_image.created",
            before=None,
            after={
                "id": str(generated_image.id),
                "task_id": str(generated_image.task_id),
                "image_type": enum_value(generated_image.image_type),
                "image_url": generated_image.image_url,
                "is_final": generated_image.is_final,
            },
            metadata={"task_id": str(task.id), "image_type": enum_value(image_type)},
        )
        task.updated_at = now
        return generated_image

    before = {
        "id": str(existing.id),
        "task_id": str(existing.task_id),
        "image_type": enum_value(existing.image_type),
        "image_url": existing.image_url,
        "prompt_used": existing.prompt_used,
        "metadata": existing.metadata_json or {},
        "is_final": existing.is_final,
    }
    history = _generation_history(existing)
    history.append(
        {
            "image_url": existing.image_url,
            "prompt_used": existing.prompt_used,
            "metadata": existing.metadata_json or {},
            "saved_at": now.isoformat(),
        }
    )
    existing.angle = angle
    existing.image_bucket = str(metadata.get("bucket") or current_app.config["SUPABASE_STORAGE_BUCKET"])
    existing.image_url = image_url
    existing.prompt_used = prompt_used
    existing.metadata_json = {
        **(existing.metadata_json or {}),
        **metadata,
        "storage_path": storage_path,
        "history": history,
    }
    existing.is_final = is_final
    existing.updated_at = now
    add_entity_audit_log(
        actor=actor,
        entity_type="generated_image",
        entity_id=existing.id,
        action="generated_image.updated",
        before=before,
        after={
            "id": str(existing.id),
            "task_id": str(existing.task_id),
            "image_type": enum_value(existing.image_type),
            "image_url": existing.image_url,
            "is_final": existing.is_final,
        },
        metadata={"task_id": str(task.id), "image_type": enum_value(image_type)},
    )
    task.updated_at = now
    return existing


def delete_generated_image(*, actor: User, task: Task, image: GeneratedImage) -> None:
    before = {
        "id": str(image.id),
        "task_id": str(image.task_id),
        "image_type": enum_value(image.image_type),
        "image_url": image.image_url,
        "metadata": image.metadata_json or {},
        "is_final": image.is_final,
    }
    storage_path = (image.metadata_json or {}).get("storage_path") if isinstance(image.metadata_json, dict) else None
    if storage_path:
        delete_storage_object(bucket=image.image_bucket, path=str(storage_path))
    add_entity_audit_log(
        actor=actor,
        entity_type="generated_image",
        entity_id=image.id,
        action="generated_image.deleted",
        before=before,
        after={},
        metadata={"task_id": str(task.id), "image_type": enum_value(image.image_type)},
    )
    db.session.delete(image)
    task.updated_at = now_utc()
    db.session.commit()


def mark_generated_image_final(*, actor: User, task: Task, image: GeneratedImage) -> GeneratedImage:
    before = {
        "id": str(image.id),
        "task_id": str(image.task_id),
        "image_type": enum_value(image.image_type),
        "image_url": image.image_url,
        "metadata": image.metadata_json or {},
        "is_final": image.is_final,
    }
    image.is_final = True
    image.updated_at = now_utc()
    task.updated_at = now_utc()
    add_entity_audit_log(
        actor=actor,
        entity_type="generated_image",
        entity_id=image.id,
        action="generated_image.marked_final",
        before=before,
        after={
            "id": str(image.id),
            "task_id": str(image.task_id),
            "image_type": enum_value(image.image_type),
            "image_url": image.image_url,
            "is_final": image.is_final,
        },
        metadata={"task_id": str(task.id), "image_type": enum_value(image.image_type)},
    )
    db.session.commit()
    return image


def assign_task(actor: User, task: Task, assignee_id: uuid.UUID) -> Task:
    if enum_value(task.status) == TaskStatus.ACCEPTED.value:
        raise ApiError("accepted_task_cannot_be_assigned", 409)
    assignee = get_active_user_or_404(assignee_id)
    before = snapshot_task(task)
    task.assigned_to = assignee.id
    task.status = TaskStatus.ASSIGNED
    task.assigned_at = now_utc()
    task.updated_at = now_utc()
    email_context = build_task_email_context(
        task_id=str(task.id),
        task_title=task.title,
        assignee_email=assignee.email,
        assignee_name=assignee.full_name,
    )
    add_audit_log(actor=actor, task=task, action="task.assigned", before=before, metadata={"assignee_id": str(assignee.id)})
    commit_and_restore_context(actor)
    trigger_task_assigned_email(email_context)
    return task


def start_task(actor: User, task: Task) -> Task:
    ensure_assigned_user(task, actor)
    if enum_value(task.status) not in {TaskStatus.ASSIGNED.value, TaskStatus.REVISION_REQUESTED.value}:
        raise ApiError("task_cannot_be_started", 409)
    before = snapshot_task(task)
    task.status = TaskStatus.IN_PROGRESS
    task.started_at = now_utc()
    task.updated_at = now_utc()
    add_audit_log(actor=actor, task=task, action="task.started", before=before)
    commit_and_restore_context(actor)
    return task


def submit_task(actor: User, task: Task, payload: dict[str, Any]) -> Task:
    ensure_assigned_user(task, actor)
    if enum_value(task.status) != TaskStatus.IN_PROGRESS.value:
        raise ApiError("task_cannot_be_submitted", 409)
    present_types = {enum_value(image.image_type) for image in task.generated_images}
    required_types = _required_generation_type_values()
    missing_types = sorted(required_types - present_types)
    if missing_types:
        raise ApiError("task_generation_incomplete", 409)
    if any(not image.is_final for image in task.generated_images):
        raise ApiError("task_generation_not_finalized", 409)
    before = snapshot_task(task)
    task.status = TaskStatus.SUBMITTED
    task.submission_notes = str(payload.get("submission_notes") or "")
    task.submitted_at = now_utc()
    task.updated_at = now_utc()
    email_context = build_task_email_context(
        task_id=str(task.id),
        task_title=task.title,
        assignee_name=actor.full_name or actor.email,
        creator_email=task.creator.email if task.creator else None,
    )
    add_audit_log(actor=actor, task=task, action="task.submitted", before=before)
    commit_and_restore_context(actor)
    trigger_task_submitted_email(email_context)
    return task


def accept_task(actor: User, task: Task, payload: dict[str, Any]) -> Task:
    if enum_value(task.status) != TaskStatus.SUBMITTED.value:
        raise ApiError("task_cannot_be_accepted", 409)
    before = snapshot_task(task)
    task.status = TaskStatus.ACCEPTED
    task.review_notes = str(payload.get("review_notes") or "")
    task.accepted_at = now_utc()
    task.updated_at = now_utc()
    email_context = build_task_email_context(
        task_id=str(task.id),
        task_title=task.title,
        assignee_email=task.assignee.email if task.assignee else None,
        assignee_name=task.assignee.full_name if task.assignee else None,
        review_notes=task.review_notes,
        status=task.status,
    )
    add_audit_log(actor=actor, task=task, action="task.accepted", before=before)
    commit_and_restore_context(actor)
    trigger_task_review_email(email_context)
    return task


def request_revision(actor: User, task: Task, payload: dict[str, Any]) -> Task:
    if enum_value(task.status) not in {TaskStatus.SUBMITTED.value, TaskStatus.ACCEPTED.value}:
        raise ApiError("task_cannot_request_revision", 409)
    review_notes = str(payload.get("review_notes") or "").strip()
    if not review_notes:
        raise ApiError("review_notes_required", 400)
    before = snapshot_task(task)
    task.status = TaskStatus.REVISION_REQUESTED
    task.review_notes = review_notes
    task.revision_requested_at = now_utc()
    task.updated_at = now_utc()
    email_context = build_task_email_context(
        task_id=str(task.id),
        task_title=task.title,
        assignee_email=task.assignee.email if task.assignee else None,
        assignee_name=task.assignee.full_name if task.assignee else None,
        review_notes=task.review_notes,
        status=task.status,
    )
    add_audit_log(actor=actor, task=task, action="task.revision_requested", before=before)
    commit_and_restore_context(actor)
    trigger_task_review_email(email_context)
    return task


def delete_task(actor: User, task: Task) -> None:
    before = snapshot_task(task)
    add_audit_log(
        actor=actor,
        task=task,
        action="task.deleted",
        before=before,
        after={},
        metadata={"deleted_task_id": str(task.id)},
    )
    db.session.delete(task)
    db.session.commit()


def list_admin_tasks() -> list[Task]:
    return db.session.scalars(
        select(Task)
        .options(selectinload(Task.creator), selectinload(Task.assignee), selectinload(Task.generated_images))
        .order_by(Task.created_at.desc())
    ).all()


def list_assigned_tasks(user: User) -> list[Task]:
    return db.session.scalars(
        select(Task)
        .options(selectinload(Task.creator), selectinload(Task.assignee), selectinload(Task.generated_images))
        .where(Task.assigned_to == user.id)
        .order_by(Task.created_at.desc())
    ).all()


def list_task_generations(task: Task, user: User) -> list[dict[str, Any]]:
    if user.role != UserRole.ADMIN and enum_value(user.role) != UserRole.ADMIN.value:
        ensure_assigned_user(task, user)
    images = db.session.scalars(
        select(GeneratedImage).where(GeneratedImage.task_id == task.id).order_by(GeneratedImage.created_at.desc())
    ).all()
    return [serialize_generated_image(image) for image in images]

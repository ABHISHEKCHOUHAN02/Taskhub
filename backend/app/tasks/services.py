from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa
from flask import current_app
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..extensions import db
from ..models.audit_log import AuditLog
from ..models.enums import TaskStatus, UserRole
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
    def __init__(self, code: str, status_code: int = 400):
        super().__init__(code)
        self.code = code
        self.status_code = status_code


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
        raise ApiError(f"{field}_invalid", 400) from exc
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


def add_audit_log(
    *,
    actor: User,
    task: Task,
    action: str,
    before: dict[str, Any] | None,
    metadata: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    db.session.add(
        AuditLog(
            actor_user_id=actor.id,
            entity_type="task",
            entity_id=task.id,
            action=action,
            before_data=before,
            after_data=snapshot_task(task) if after is None else after,
            metadata_json=metadata or {},
        )
    )


def create_task(actor: User, payload: dict[str, Any]) -> Task:
    title = str(payload.get("title") or "").strip()
    product_image_url = str(payload.get("product_image_url") or "").strip()
    if not title:
        raise ApiError("title_required", 400)
    if not product_image_url:
        raise ApiError("product_image_url_required", 400)

    assignee_id = payload.get("assigned_to")
    assignee = get_active_user_or_404(parse_uuid(str(assignee_id), "assigned_to")) if assignee_id else None
    created_at = now_utc()
    task = Task(
        title=title,
        description=str(payload.get("description") or ""),
        status=TaskStatus.ASSIGNED if assignee else TaskStatus.PENDING,
        created_by=actor.id,
        assigned_to=assignee.id if assignee else None,
        product_image_bucket=str(payload.get("product_image_bucket") or current_app.config["SUPABASE_STORAGE_BUCKET"]),
        product_image_url=product_image_url,
        product_image_metadata=payload.get("product_image_metadata") or {},
        due_at=parse_datetime(payload.get("due_at"), "due_at"),
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
    if email_context:
        trigger_task_assigned_email(email_context)
    return task


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
        .options(selectinload(Task.creator), selectinload(Task.assignee))
        .order_by(Task.created_at.desc())
    ).all()


def list_assigned_tasks(user: User) -> list[Task]:
    return db.session.scalars(
        select(Task)
        .options(selectinload(Task.creator), selectinload(Task.assignee))
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

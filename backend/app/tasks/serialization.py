from __future__ import annotations

from datetime import datetime
from typing import Any

from ..models.generated_image import GeneratedImage
from ..models.task import Task
from ..models.user import User


def enum_value(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value)


def isoformat(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def serialize_user(user: User | None) -> dict[str, Any] | None:
    if user is None:
        return None
    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "avatar_url": user.avatar_url,
        "role": enum_value(user.role),
    }


def serialize_generated_image(image: GeneratedImage) -> dict[str, Any]:
    return {
        "id": str(image.id),
        "task_id": str(image.task_id),
        "image_type": enum_value(image.image_type),
        "angle": image.angle,
        "image_bucket": image.image_bucket,
        "image_url": image.image_url,
        "prompt_used": image.prompt_used,
        "metadata": image.metadata_json or {},
        "is_final": image.is_final,
        "created_by": str(image.created_by),
        "created_at": isoformat(image.created_at),
        "updated_at": isoformat(image.updated_at),
    }


def serialize_task(task: Task, *, include_images: bool = False) -> dict[str, Any]:
    payload = {
        "id": str(task.id),
        "title": task.title,
        "description": task.description,
        "status": enum_value(task.status),
        "created_by": str(task.created_by),
        "assigned_to": str(task.assigned_to) if task.assigned_to else None,
        "creator": serialize_user(task.creator),
        "assignee": serialize_user(task.assignee),
        "product_image_bucket": task.product_image_bucket,
        "product_image_url": task.product_image_url,
        "product_image_metadata": task.product_image_metadata or {},
        "submission_notes": task.submission_notes,
        "review_notes": task.review_notes,
        "due_at": isoformat(task.due_at),
        "assigned_at": isoformat(task.assigned_at),
        "started_at": isoformat(task.started_at),
        "submitted_at": isoformat(task.submitted_at),
        "accepted_at": isoformat(task.accepted_at),
        "revision_requested_at": isoformat(task.revision_requested_at),
        "created_at": isoformat(task.created_at),
        "updated_at": isoformat(task.updated_at),
    }
    if include_images:
        payload["generated_images"] = [serialize_generated_image(image) for image in task.generated_images]
    return payload


def snapshot_task(task: Task) -> dict[str, Any]:
    return serialize_task(task, include_images=False)

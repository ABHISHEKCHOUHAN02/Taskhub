from __future__ import annotations

import uuid
from typing import Any

from flask import current_app

from .ai import (
    build_generation_metadata,
    build_generated_image_path,
    build_negative_prompt,
    build_positive_prompt,
    download_remote_image,
    extract_product_image,
    generation_angle,
    get_image_provider,
    sha256_hex,
    upload_generated_image,
)
from .celery_app import celery
from .models.enums import GeneratedImageType
from .tasks.email import _post_resend
from .tasks.services import (
    ApiError,
    get_active_user_or_404,
    get_task_or_404,
    now_utc,
    save_generated_image,
    set_rls_context,
)


@celery.task(name="taskhub.send_resend_email")
def send_resend_email(payload: dict[str, Any]) -> None:
    _post_resend(payload)


@celery.task(name="taskhub.generate_task_image", bind=True)
def generate_task_image(self, task_id: str, actor_user_id: str, image_type: str) -> dict[str, Any]:
    def progress(step: str) -> None:
        self.update_state(state="STARTED", meta={"step": step, "image_type": image_type})
        current_app.logger.info("Generation job %s for %s: %s", self.request.id, image_type, step)

    progress("loading task")
    actor_uuid = uuid.UUID(str(actor_user_id))
    task_uuid = uuid.UUID(str(task_id))
    actor = get_active_user_or_404(actor_uuid)

    set_rls_context(actor)
    task = get_task_or_404(task_uuid)

    if task.assigned_to is None and getattr(actor.role, "value", str(actor.role)) != "admin":
        raise ApiError("task_not_assigned", 409)
    if getattr(task.status, "value", str(task.status)) == "accepted":
        raise ApiError("accepted_task_cannot_generate", 409)

    try:
        normalized_type = GeneratedImageType(image_type)
    except ValueError as exc:
        raise ApiError("image_type_invalid", 400) from exc
    progress("downloading source image")
    source_bytes, source_content_type = download_remote_image(task.product_image_url)
    progress("removing source background")
    extracted_bytes = extract_product_image(source_bytes)
    progress("preparing generation prompt")
    provider = get_image_provider()
    positive_prompt = build_positive_prompt(task, normalized_type)
    negative_prompt = build_negative_prompt(task, normalized_type)
    progress("calling image model")
    generated_bytes = provider.image_to_image(
        image_bytes=extracted_bytes,
        prompt=positive_prompt,
        negative_prompt=negative_prompt,
    )
    progress("uploading generated image")
    storage_path = build_generated_image_path(str(task.id), normalized_type.value, job_id=self.request.id)
    public_url = upload_generated_image(
        bucket=current_app.config["SUPABASE_STORAGE_BUCKET"],
        path=storage_path,
        image_bytes=generated_bytes,
    )
    source_hash = sha256_hex(extracted_bytes)
    metadata = build_generation_metadata(
        task=task,
        image_type=normalized_type,
        prompt=positive_prompt,
        negative_prompt=negative_prompt,
        source_url=task.product_image_url,
        source_sha256=source_hash,
        provider=current_app.config["HF_PROVIDER"],
        model_id=current_app.config["HF_MODEL_ID"],
        job_id=self.request.id,
    )
    generated_image = save_generated_image(
        actor=actor,
        task=task,
        image_type=normalized_type,
        angle=generation_angle(normalized_type),
        image_url=public_url,
        storage_path=storage_path,
        prompt_used=positive_prompt,
        metadata=metadata,
        is_final=False,
    )
    progress("saving generation")
    task.updated_at = now_utc()
    from .extensions import db

    db.session.commit()
    return {
        "task_id": str(task.id),
        "image_type": normalized_type.value,
        "generated_image_id": str(generated_image.id),
        "image_url": public_url,
        "storage_path": storage_path,
        "source_content_type": source_content_type,
    }

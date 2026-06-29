from __future__ import annotations

from flask import current_app

from .celery_app import celery


class QueueUnavailableError(RuntimeError):
    pass


def _safe_send_task(
    task_name: str,
    *,
    args: list | None = None,
    kwargs: dict | None = None,
    ignore_result: bool = False,
) -> object | None:
    try:
        return celery.send_task(task_name, args=args or [], kwargs=kwargs or {}, ignore_result=ignore_result)
    except Exception as exc:
        current_app.logger.warning("Background job skipped for %s: %s", task_name, exc)
        return None


def queue_resend_email(payload: dict) -> object | None:
    return _safe_send_task("taskhub.send_resend_email", args=[payload], ignore_result=True)


def queue_generation_job(*, task_id: str, actor_user_id: str, image_type: str) -> object | None:
    result = _safe_send_task(
        "taskhub.generate_task_image",
        args=[task_id, actor_user_id, image_type],
    )
    if result is None:
        raise QueueUnavailableError("generation_queue_unavailable")
    return result

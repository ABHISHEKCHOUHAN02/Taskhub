from __future__ import annotations

import json
from html import escape
from typing import Any
from urllib import request as urlrequest
from urllib.error import URLError

from flask import current_app

from .serialization import enum_value


def build_task_email_context(
    *,
    task_id: str,
    task_title: str,
    assignee_email: str | None = None,
    assignee_name: str | None = None,
    creator_email: str | None = None,
    review_notes: str | None = None,
    status: object | None = None,
) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "task_title": task_title,
        "assignee_email": assignee_email,
        "assignee_name": assignee_name or assignee_email or "TaskHub user",
        "creator_email": creator_email,
        "review_notes": review_notes or "",
        "status": enum_value(status) if status is not None else "",
    }


def _task_url(task_id: str) -> str:
    return f"{current_app.config['FRONTEND_URL']}/tasks/{task_id}"


def _post_resend(payload: dict[str, Any]) -> None:
    api_key = current_app.config.get("RESEND_API_KEY")
    if not api_key:
        current_app.logger.info("Email trigger skipped because RESEND_API_KEY is not configured: %s", payload["subject"])
        return

    request = urlrequest.Request(
        "https://api.resend.com/emails",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlrequest.urlopen(request, timeout=10) as response:
            if response.status >= 400:
                current_app.logger.warning("Resend returned HTTP %s for %s", response.status, payload["subject"])
    except URLError as exc:
        current_app.logger.warning("Email trigger failed for %s: %s", payload["subject"], exc)


def trigger_task_assigned_email(context: dict[str, Any]) -> None:
    if not context.get("assignee_email"):
        return
    task_url = _task_url(context["task_id"])
    subject = f"Task assigned: {context['task_title']}"
    assignee_name = escape(context["assignee_name"])
    task_title = escape(context["task_title"])
    html = (
        f"<p>Hello {assignee_name},</p>"
        f"<p>You have been assigned <strong>{task_title}</strong> in TaskHub.</p>"
        f"<p><a href=\"{task_url}\">Open the task</a></p>"
    )
    _post_resend(
        {
            "from": current_app.config["EMAIL_FROM"],
            "to": [context["assignee_email"]],
            "subject": subject,
            "html": html,
        }
    )


def trigger_task_submitted_email(context: dict[str, Any]) -> None:
    if not context.get("creator_email"):
        return
    task_url = _task_url(context["task_id"])
    subject = f"Task submitted: {context['task_title']}"
    assignee_name = escape(context["assignee_name"])
    task_title = escape(context["task_title"])
    html = (
        f"<p>{assignee_name} submitted <strong>{task_title}</strong>.</p>"
        f"<p><a href=\"{task_url}\">Review the submission</a></p>"
    )
    _post_resend(
        {
            "from": current_app.config["EMAIL_FROM"],
            "to": [context["creator_email"]],
            "subject": subject,
            "html": html,
        }
    )


def trigger_task_review_email(context: dict[str, Any]) -> None:
    if not context.get("assignee_email"):
        return
    status = context["status"]
    task_url = _task_url(context["task_id"])
    subject = f"Task {status.replace('_', ' ')}: {context['task_title']}"
    assignee_name = escape(context["assignee_name"])
    task_title = escape(context["task_title"])
    review_notes = escape(context["review_notes"])
    html = (
        f"<p>Hello {assignee_name},</p>"
        f"<p>Your task <strong>{task_title}</strong> is now <strong>{status.replace('_', ' ')}</strong>.</p>"
        f"<p>{review_notes}</p>"
        f"<p><a href=\"{task_url}\">Open the task</a></p>"
    )
    _post_resend(
        {
            "from": current_app.config["EMAIL_FROM"],
            "to": [context["assignee_email"]],
            "subject": subject,
            "html": html,
        }
    )

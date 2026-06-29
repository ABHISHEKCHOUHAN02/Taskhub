from __future__ import annotations

import json
from html import escape
from typing import Any

from flask import current_app

from ..auth.config import get_admin_emails
from ..queue import queue_resend_email
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

    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    from_addr = payload["from"]
    to_addrs = payload["to"]
    subject = payload["subject"]
    html_body = payload["html"]

    msg = MIMEMultipart("alternative")
    msg["From"] = from_addr
    msg["To"] = ", ".join(to_addrs) if isinstance(to_addrs, list) else to_addrs
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.resend.com", 465, timeout=10) as server:
            server.login("resend", api_key)
            server.sendmail(from_addr, to_addrs, msg.as_string())
        current_app.logger.info("Email sent via SMTP: %s", subject)
    except Exception as exc:
        current_app.logger.warning("Email trigger failed for %s: %s", subject, exc)


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
    queue_resend_email(
        {
            "from": current_app.config["EMAIL_FROM"],
            "to": [context["assignee_email"]],
            "subject": subject,
            "html": html,
        }
    )


def trigger_task_submitted_email(context: dict[str, Any]) -> None:
    recipients = []
    if context.get("creator_email"):
        recipients.append(context["creator_email"])
    recipients.extend(get_admin_emails())
    recipients = list(dict.fromkeys(email for email in recipients if email))
    if not recipients:
        return
    task_url = _task_url(context["task_id"])
    subject = f"Task submitted: {context['task_title']}"
    assignee_name = escape(context["assignee_name"])
    task_title = escape(context["task_title"])
    html = (
        f"<p>{assignee_name} submitted <strong>{task_title}</strong>.</p>"
        f"<p><a href=\"{task_url}\">Review the submission</a></p>"
    )
    queue_resend_email(
        {
            "from": current_app.config["EMAIL_FROM"],
            "to": recipients,
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
    queue_resend_email(
        {
            "from": current_app.config["EMAIL_FROM"],
            "to": [context["assignee_email"]],
            "subject": subject,
            "html": html,
        }
    )

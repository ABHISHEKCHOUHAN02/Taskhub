from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from flask import current_app
from sqlalchemy import select, func

from ..extensions import db
from ..models.enums import UserRole
from ..models.user import User
from .config import get_admin_emails


def _now() -> datetime:
    return datetime.now(timezone.utc)


def resolve_role(email: str) -> UserRole:
    admin_emails = {item.lower() for item in get_admin_emails()}
    if email.lower() in admin_emails:
        return UserRole.ADMIN

    existing_admin_count = db.session.scalar(
        select(func.count()).select_from(User).where(User.role == UserRole.ADMIN)
    )
    if not existing_admin_count:
        return UserRole.ADMIN

    return UserRole.USER


def upsert_oauth_user(
    *,
    provider: str,
    subject: str,
    email: str,
    full_name: str,
    avatar_url: str | None,
    oauth_metadata: dict[str, Any],
) -> User:
    user = db.session.scalar(
        select(User).where(User.oauth_provider == provider, User.oauth_subject == subject)
    )
    if user is None:
        user = db.session.scalar(select(User).where(User.email == email))

    role = user.role if user is not None else resolve_role(email)
    if user is None:
        user = User(
            email=email,
            full_name=full_name or email,
            avatar_url=avatar_url,
            oauth_provider=provider,
            oauth_subject=subject,
            oauth_metadata=oauth_metadata,
            role=role,
            is_active=True,
            last_login_at=_now(),
        )
        db.session.add(user)
    else:
        user.email = email
        user.full_name = full_name or user.full_name or email
        user.avatar_url = avatar_url
        user.oauth_provider = provider
        user.oauth_subject = subject
        user.oauth_metadata = oauth_metadata
        user.role = role
        user.is_active = True
        user.last_login_at = _now()

    db.session.commit()
    return user


def is_admin(user: User | None) -> bool:
    return bool(user and (user.role == UserRole.ADMIN or user.role == "admin"))


def is_user(user: User | None) -> bool:
    return bool(user and (user.role == UserRole.USER or user.role == "user"))


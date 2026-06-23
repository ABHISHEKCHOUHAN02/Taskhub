from __future__ import annotations

from dataclasses import dataclass

from flask import Response, session

from ..models.user import User
from .config import get_cookie_domain


AUTH_COOKIE_KEYS = (
    "taskhub_role",
    "taskhub_user_id",
    "taskhub_user_email",
    "taskhub_user_name",
)


@dataclass(frozen=True)
class AuthSession:
    user_id: str
    role: str
    email: str
    full_name: str


def store_auth_session(user: User) -> None:
    session.clear()
    session.permanent = True
    session["user_id"] = str(user.id)
    session["role"] = user.role.value if hasattr(user.role, "value") else str(user.role)
    session["email"] = user.email
    session["full_name"] = user.full_name


def clear_auth_session() -> None:
    session.clear()


def build_session_cookies(response: Response, user: User, secure: bool) -> Response:
    cookie_domain = get_cookie_domain()
    cookie_options = {
        "httponly": True,
        "secure": secure,
        "samesite": "Lax",
        "domain": cookie_domain,
        "path": "/",
    }
    response.set_cookie("taskhub_role", user.role.value if hasattr(user.role, "value") else str(user.role), **cookie_options)
    response.set_cookie("taskhub_user_id", str(user.id), **cookie_options)
    response.set_cookie("taskhub_user_email", user.email, **cookie_options)
    response.set_cookie("taskhub_user_name", user.full_name or user.email, **cookie_options)
    return response


def clear_session_cookies(response: Response) -> Response:
    cookie_domain = get_cookie_domain()
    for key in AUTH_COOKIE_KEYS:
        response.delete_cookie(key, domain=cookie_domain, path="/")
    return response


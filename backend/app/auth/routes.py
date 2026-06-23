from __future__ import annotations

import os
import uuid
from functools import wraps

from flask import Blueprint, Response, current_app, g, jsonify, redirect, request, session

from ..extensions import db
from ..models.enums import UserRole
from ..models.user import User
from .config import get_frontend_url
from .oauth import (
    OAuthProvider,
    build_authorize_url,
    exchange_code_for_token,
    fetch_json,
    generate_state,
)
from .services import upsert_oauth_user
from .session import build_session_cookies, clear_auth_session, clear_session_cookies, store_auth_session

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _secure_cookie_flag() -> bool:
    return os.getenv("SESSION_COOKIE_SECURE", "false").lower() in {"1", "true", "yes", "on"}


def _provider_config(provider_name: str) -> OAuthProvider:
    provider_name = provider_name.lower()
    if provider_name == "google":
        return OAuthProvider(
            name="google",
            client_id=os.environ["GOOGLE_CLIENT_ID"],
            client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
            authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
            token_url="https://oauth2.googleapis.com/token",
            userinfo_url="https://www.googleapis.com/oauth2/v2/userinfo",
            scope="openid email profile",
            redirect_uri=os.environ["GOOGLE_REDIRECT_URI"],
        )
    if provider_name == "github":
        return OAuthProvider(
            name="github",
            client_id=os.environ["GITHUB_CLIENT_ID"],
            client_secret=os.environ["GITHUB_CLIENT_SECRET"],
            authorize_url="https://github.com/login/oauth/authorize",
            token_url="https://github.com/login/oauth/access_token",
            userinfo_url="https://api.github.com/user",
            scope="read:user user:email",
            redirect_uri=os.environ["GITHUB_REDIRECT_URI"],
            extra_headers={"Accept": "application/json"},
        )
    raise ValueError(f"Unsupported OAuth provider: {provider_name}")


def _provider_callback_uri(provider_name: str) -> str:
    return f"{get_frontend_url()}/api/auth/oauth/{provider_name}/callback"


def _load_current_user() -> User | None:
    user_id = session.get("user_id")
    if not user_id:
        g.current_user = None
        return None

    try:
        user_pk = uuid.UUID(str(user_id))
    except ValueError:
        clear_auth_session()
        g.current_user = None
        return None

    user = db.session.get(User, user_pk)
    if user is None or not user.is_active:
        clear_auth_session()
        g.current_user = None
        return None

    g.current_user = user
    return user


def _current_user_or_401() -> User:
    user = getattr(g, "current_user", None) or _load_current_user()
    if user is None:
        raise PermissionError("authentication required")
    return user


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            _current_user_or_401()
        except PermissionError:
            return jsonify({"error": "authentication_required"}), 401
        return fn(*args, **kwargs)

    return wrapper


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            user = _current_user_or_401()
        except PermissionError:
            return jsonify({"error": "authentication_required"}), 401
        if user.role != UserRole.ADMIN and str(user.role) != "admin":
            return jsonify({"error": "admin_required"}), 403
        return fn(*args, **kwargs)

    return wrapper


@auth_bp.before_app_request
def _attach_current_user() -> None:
    if request.path.startswith("/api/auth/"):
        return
    _load_current_user()


@auth_bp.route("/oauth/<provider>/start", methods=["GET"])
def oauth_start(provider: str):
    provider_cfg = _provider_config(provider)
    state = generate_state()
    session["oauth_state"] = state
    session["oauth_provider"] = provider_cfg.name
    session["oauth_next"] = request.args.get("next") or "/dashboard"
    auth_url = build_authorize_url(provider_cfg, state)
    return redirect(auth_url)


@auth_bp.route("/oauth/<provider>/callback", methods=["GET", "POST"])
@auth_bp.route("/oauth/callback", methods=["GET", "POST"])
def oauth_callback(provider: str | None = None):
    provider_name = (provider or request.args.get("provider") or request.form.get("provider") or session.get("oauth_provider") or "").lower()
    if not provider_name:
        return jsonify({"error": "provider_required"}), 400

    provider_cfg = _provider_config(provider_name)
    code = request.values.get("code")
    state = request.values.get("state")
    expected_state = session.get("oauth_state")

    if not code:
        return jsonify({"error": "code_required"}), 400
    if not state or not expected_state or state != expected_state:
        return jsonify({"error": "invalid_state"}), 400

    token_payload = exchange_code_for_token(provider_cfg, code)
    access_token = token_payload.get("access_token")
    if not access_token:
        return jsonify({"error": "token_exchange_failed"}), 400

    if provider_name == "google":
        profile = fetch_json(
            provider_cfg.userinfo_url,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        subject = str(profile.get("sub") or "")
        email = str(profile.get("email") or "")
        full_name = str(profile.get("name") or profile.get("given_name") or email)
        avatar_url = profile.get("picture")
        oauth_metadata = profile if isinstance(profile, dict) else {}
    else:
        profile = fetch_json(
            provider_cfg.userinfo_url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
            },
        )
        emails = fetch_json(
            "https://api.github.com/user/emails",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
            },
        )
        primary_email = ""
        if isinstance(emails, list):
            for item in emails:
                if item.get("primary") and item.get("verified"):
                    primary_email = str(item.get("email") or "")
                    break
            if not primary_email and emails:
                primary_email = str(emails[0].get("email") or "")
        subject = str(profile.get("id") or "")
        email = primary_email or str(profile.get("email") or "")
        full_name = str(profile.get("name") or profile.get("login") or email)
        avatar_url = profile.get("avatar_url")
        oauth_metadata = {"profile": profile, "emails": emails}

    if not subject or not email:
        return jsonify({"error": "oauth_profile_incomplete"}), 400

    user = upsert_oauth_user(
        provider=provider_name,
        subject=subject,
        email=email,
        full_name=full_name,
        avatar_url=avatar_url,
        oauth_metadata=oauth_metadata,
    )

    store_auth_session(user)

    response = redirect(
        f"{get_frontend_url()}/admin" if (user.role == UserRole.ADMIN or str(user.role) == "admin") else f"{get_frontend_url()}/dashboard"
    )
    response = build_session_cookies(response, user, secure=_secure_cookie_flag())
    return response


@auth_bp.route("/me", methods=["GET"])
@login_required
def me():
    user = _current_user_or_401()
    return jsonify(
        {
            "authenticated": True,
            "user": {
                "id": str(user.id),
                "email": user.email,
                "full_name": user.full_name,
                "avatar_url": user.avatar_url,
                "role": user.role.value if hasattr(user.role, "value") else str(user.role),
                "is_active": user.is_active,
            },
        }
    )


@auth_bp.route("/logout", methods=["POST"])
def logout():
    clear_auth_session()
    response = jsonify({"ok": True})
    response = clear_session_cookies(response)
    response.delete_cookie(current_app.config["SESSION_COOKIE_NAME"])
    response.status_code = 200
    if request.accept_mimetypes.best == "text/html":
        response = redirect(get_frontend_url())
        response = clear_session_cookies(response)
        response.delete_cookie(current_app.config["SESSION_COOKIE_NAME"])
    return response

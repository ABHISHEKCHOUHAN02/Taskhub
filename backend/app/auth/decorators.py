from __future__ import annotations

import uuid
from functools import wraps

from flask import g, jsonify, session

from ..extensions import db
from ..models.enums import UserRole
from ..models.user import User
from .session import clear_auth_session


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

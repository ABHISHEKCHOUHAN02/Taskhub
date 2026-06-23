import os


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def get_admin_emails() -> list[str]:
    return _split_csv(os.getenv("ADMIN_EMAILS"))


def get_frontend_url() -> str:
    return os.getenv("FRONTEND_URL", "http://localhost:3000").rstrip("/")


def get_cookie_domain() -> str | None:
    value = os.getenv("SESSION_COOKIE_DOMAIN", "").strip()
    return value or None


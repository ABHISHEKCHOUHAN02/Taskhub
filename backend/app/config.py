import os
from datetime import timedelta

from dotenv import load_dotenv
from sqlalchemy.engine import make_url

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

load_dotenv(os.path.join(BASE_DIR, ".env"))
load_dotenv(os.path.join(BASE_DIR, "..", ".env"))


class BaseConfig:
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
    }

    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "change-me")
    SESSION_COOKIE_NAME = "taskhub_session"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() in {"1", "true", "yes", "on"}
    SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
    SESSION_COOKIE_DOMAIN = os.getenv("SESSION_COOKIE_DOMAIN", "").strip() or None
    PERMANENT_SESSION_LIFETIME = timedelta(seconds=int(os.getenv("SESSION_LIFETIME_SECONDS", "604800")))

    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000").rstrip("/")
    SUPABASE_STORAGE_BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "taskhub-assets")
    RESEND_API_KEY = os.getenv("RESEND_API_KEY", "").strip()
    EMAIL_FROM = os.getenv("EMAIL_FROM", "TaskHub <no-reply@example.com>").strip()

    if not SQLALCHEMY_DATABASE_URI:
        raise RuntimeError(
            "DATABASE_URL is not set. Create backend/.env with your Supabase Postgres connection string."
        )

    try:
        make_url(SQLALCHEMY_DATABASE_URI)
    except Exception as exc:  # pragma: no cover - startup validation
        raise RuntimeError(
            "DATABASE_URL is malformed. Use a URL-encoded Supabase Postgres connection string like "
            "'postgresql+psycopg://postgres:<url-encoded-password>@db.<project-ref>.supabase.co:5432/postgres?sslmode=require'."
        ) from exc


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class ProductionConfig(BaseConfig):
    DEBUG = False


def get_config():
    env = os.getenv("FLASK_ENV", "development").lower()
    if env == "production":
        return ProductionConfig
    return DevelopmentConfig

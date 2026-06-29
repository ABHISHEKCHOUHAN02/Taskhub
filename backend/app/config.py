import os
from datetime import timedelta
from urllib.parse import urlparse

from dotenv import load_dotenv
from sqlalchemy.engine import make_url

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

load_dotenv(os.path.join(BASE_DIR, ".env"))
load_dotenv(os.path.join(BASE_DIR, "..", ".env"))


def redis_url_from_env() -> str:
    redis_url = (os.getenv("REDIS_URL") or "redis://localhost:6379/0").strip()
    if redis_url.startswith("redis-cli"):
        parts = redis_url.split()
        redis_url = next((part for part in parts if part.startswith(("redis://", "rediss://"))), "")

    parsed = urlparse(redis_url)
    if parsed.scheme not in {"redis", "rediss"} or not parsed.hostname:
        raise RuntimeError(
            "REDIS_URL is malformed. Use a Redis URL like "
            "'redis://default:<password>@<host>:6379/0' or 'rediss://default:<password>@<host>:6379/0'."
        )
    if not parsed.path:
        redis_url = f"{redis_url}/0"
    return redis_url


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
    SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    REDIS_URL = redis_url_from_env()
    CELERY_BROKER_URL = REDIS_URL
    CELERY_RESULT_BACKEND = REDIS_URL
    RESEND_API_KEY = os.getenv("RESEND_API_KEY", "").strip()
    EMAIL_FROM = os.getenv("EMAIL_FROM", "TaskHub <no-reply@example.com>").strip()
    AI_PROVIDER = os.getenv("AI_PROVIDER", "huggingface").strip().lower()
    HF_TOKEN = os.getenv("HF_TOKEN", os.getenv("HUGGINGFACE_HUB_TOKEN", "")).strip()
    HF_PROVIDER = os.getenv("HF_PROVIDER", "hf-inference").strip()
    HF_MODEL_ID = os.getenv("HF_MODEL_ID", "black-forest-labs/FLUX.1-Kontext-dev").strip()
    AI_IMAGE_SIZE = os.getenv("AI_IMAGE_SIZE", "1024x1024").strip()
    AI_IMAGE_QUALITY = os.getenv("AI_IMAGE_QUALITY", "high").strip().lower()

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
    LOCAL_STORAGE_FALLBACK = True


class ProductionConfig(BaseConfig):
    DEBUG = False
    LOCAL_STORAGE_FALLBACK = os.getenv("LOCAL_STORAGE_FALLBACK", "false").lower() in {"1", "true", "yes", "on"}


def get_config():
    env = os.getenv("FLASK_ENV", "development").lower()
    if env == "production":
        return ProductionConfig
    return DevelopmentConfig

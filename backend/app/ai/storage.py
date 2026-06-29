from __future__ import annotations

import hashlib
import os
from io import BytesIO
from urllib.parse import quote

import requests
from PIL import Image
from rembg import remove

from flask import current_app


class StorageUploadError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 502):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def download_remote_image(url: str) -> tuple[bytes, str]:
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    content_type = response.headers.get("content-type", "application/octet-stream")
    return response.content, content_type


def extract_product_image(image_bytes: bytes) -> bytes:
    extracted = remove(image_bytes)
    if isinstance(extracted, str):
        extracted = extracted.encode("utf-8")
    image = Image.open(BytesIO(extracted)).convert("RGBA")
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_generated_image_path(task_id: str, image_type: str, job_id: str | None = None) -> str:
    suffix = job_id or hashlib.sha1(os.urandom(32)).hexdigest()
    return f"tasks/{task_id}/generated/{image_type}/{suffix}.png"


def build_task_source_image_path(task_id: str, filename: str | None = None) -> str:
    stem = hashlib.sha1(os.urandom(32)).hexdigest()
    if filename:
        _, ext = os.path.splitext(filename)
        ext = ext.lower().strip()
        if ext in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".tif", ".tiff", ".bmp"}:
            return f"tasks/{task_id}/source/{stem}{ext}"
    return f"tasks/{task_id}/source/{stem}.png"


def upload_generated_image(*, bucket: str, path: str, image_bytes: bytes, content_type: str = "image/png") -> str:
    return upload_storage_object(bucket=bucket, path=path, data=image_bytes, content_type=content_type)


def _supabase_config() -> tuple[str, str]:
    supabase_url = str(current_app.config.get("SUPABASE_URL", "")).rstrip("/")
    service_key = str(current_app.config.get("SUPABASE_SERVICE_ROLE_KEY", "")).strip()
    if not supabase_url:
        raise StorageUploadError("storage_not_configured", "SUPABASE_URL is not configured", 500)
    if not service_key:
        raise StorageUploadError("storage_not_configured", "SUPABASE_SERVICE_ROLE_KEY is not configured", 500)
    return supabase_url, service_key


def _supabase_headers(service_key: str, *, content_type: str | None = None, upsert: bool = False) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {service_key}",
        "apikey": service_key,
    }
    if content_type:
        headers["Content-Type"] = content_type
    if upsert:
        headers["x-upsert"] = "true"
    return headers


def _parse_supabase_error(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text or response.reason or "Storage request failed"

    if isinstance(payload, dict):
        for key in ("message", "error", "statusCode"):
            value = payload.get(key)
            if value:
                return str(value)
    return response.text or response.reason or "Storage request failed"


def _local_storage_root() -> str:
    return os.path.abspath(os.path.join(current_app.root_path, "..", "var", "uploads"))


def _local_storage_enabled() -> bool:
    explicit = os.getenv("LOCAL_STORAGE_FALLBACK", "").strip().lower()
    if explicit in {"1", "true", "yes", "on"}:
        return True
    if explicit in {"0", "false", "no", "off"}:
        return False
    if current_app.config.get("LOCAL_STORAGE_FALLBACK"):
        return True
    return bool(current_app.config.get("DEBUG"))


def _is_valid_supabase_service_key(service_key: str) -> bool:
    token = service_key.strip()
    if not token:
        return False
    lowered = token.lower()
    if lowered.startswith("replace-with") or lowered in {"changeme", "change-me", "your-service-role-key"}:
        return False
    parts = token.split(".")
    return len(parts) == 3 and all(parts)


def _prefer_local_storage() -> bool:
  if os.getenv("USE_SUPABASE_STORAGE", "").strip().lower() in {"1", "true", "yes", "on"}:
    return False
  return _local_storage_enabled()


def _upload_local_file(*, bucket: str, path: str, data: bytes) -> str:
    root = _local_storage_root()
    full_path = os.path.join(root, bucket, path.replace("/", os.sep))
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "wb") as handle:
        handle.write(data)

    port = os.getenv("PORT", "5000")
    return f"http://127.0.0.1:{port}/api/local-files/{bucket}/{quote(path, safe='/')}"


def resolve_local_file_path(*, bucket: str, path: str) -> str | None:
    root = _local_storage_root()
    full_path = os.path.join(root, bucket, path.replace("/", os.sep))
    if not os.path.isfile(full_path):
        return None
    return full_path


def ensure_storage_bucket(bucket: str) -> None:
    supabase_url, service_key = _supabase_config()

    list_response = requests.get(
        f"{supabase_url}/storage/v1/bucket",
        headers=_supabase_headers(service_key),
        timeout=30,
    )
    if list_response.ok:
        buckets = list_response.json()
        if isinstance(buckets, list) and any(item.get("id") == bucket or item.get("name") == bucket for item in buckets):
            return

    create_response = requests.post(
        f"{supabase_url}/storage/v1/bucket",
        headers=_supabase_headers(service_key, content_type="application/json"),
        json={
            "id": bucket,
            "name": bucket,
            "public": True,
        },
        timeout=30,
    )
    if create_response.ok or create_response.status_code in {409, 400}:
        return

    detail = _parse_supabase_error(create_response)
    current_app.logger.warning("Could not create storage bucket %s: %s", bucket, detail)


def upload_storage_object(*, bucket: str, path: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    normalized_content_type = content_type or "application/octet-stream"

    if _prefer_local_storage():
        current_app.logger.info("Saving %s/%s to local storage", bucket, path)
        return _upload_local_file(bucket=bucket, path=path, data=data)

    try:
        supabase_url, service_key = _supabase_config()
    except StorageUploadError:
        if _local_storage_enabled():
            current_app.logger.info("Storage not configured; saving %s/%s locally", bucket, path)
            return _upload_local_file(bucket=bucket, path=path, data=data)
        raise

    if not _is_valid_supabase_service_key(service_key):
        message = (
            "SUPABASE_SERVICE_ROLE_KEY is missing or invalid. "
            "Use the service_role JWT from Supabase → Project Settings → API."
        )
        if _local_storage_enabled():
            current_app.logger.warning("%s Using local file storage instead.", message)
            return _upload_local_file(bucket=bucket, path=path, data=data)
        raise StorageUploadError("storage_not_configured", message, 500)

    try:
        ensure_storage_bucket(bucket)

        upload_url = f"{supabase_url}/storage/v1/object/{bucket}/{quote(path, safe='/')}"
        response = requests.post(
            upload_url,
            headers=_supabase_headers(service_key, content_type=normalized_content_type, upsert=True),
            data=data,
            timeout=120,
        )
        response.raise_for_status()
        return public_storage_url(bucket=bucket, path=path)
    except StorageUploadError:
        raise
    except requests.HTTPError as exc:
        detail = _parse_supabase_error(exc.response) if exc.response is not None else str(exc)
        current_app.logger.warning("Supabase upload failed for %s/%s: %s", bucket, path, detail)

        if _local_storage_enabled():
            current_app.logger.info("Falling back to local file storage for %s/%s", bucket, path)
            return _upload_local_file(bucket=bucket, path=path, data=data)

        if exc.response is not None and exc.response.status_code == 400 and "already exists" in detail.lower():
            raise StorageUploadError("storage_asset_exists", detail, 409) from exc

        raise StorageUploadError("storage_upload_failed", detail, exc.response.status_code if exc.response is not None else 502) from exc
    except requests.RequestException as exc:
        if _local_storage_enabled():
            current_app.logger.info("Falling back to local file storage after network error for %s/%s", bucket, path)
            return _upload_local_file(bucket=bucket, path=path, data=data)
        raise StorageUploadError("storage_upload_failed", str(exc), 502) from exc


def delete_storage_object(*, bucket: str, path: str) -> None:
    local_path = resolve_local_file_path(bucket=bucket, path=path)
    if local_path and os.path.isfile(local_path):
        os.remove(local_path)
        return

    try:
        supabase_url, service_key = _supabase_config()
    except StorageUploadError:
        return

    delete_url = f"{supabase_url}/storage/v1/object/{bucket}/{quote(path, safe='/')}"
    response = requests.delete(
        delete_url,
        headers=_supabase_headers(service_key),
        timeout=60,
    )
    if response.status_code == 404:
        return
    response.raise_for_status()


def public_storage_url(*, bucket: str, path: str) -> str:
    supabase_url = str(current_app.config.get("SUPABASE_URL", "")).rstrip("/")
    return f"{supabase_url}/storage/v1/object/public/{bucket}/{quote(path, safe='/')}"

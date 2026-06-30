"""
Standalone diagnostic app for the "No open ports detected" Render issue.

WHAT THIS DOES
--------------
This is a throwaway Flask app you deploy TEMPORARILY in place of your real
wsgi.py to find out exactly which startup step is hanging. It binds the port
FIRST (so Render always sees an open port), then runs each suspect
initialization step in a background thread, logging start/finish/timeout for
each one. Whichever step never logs "FINISHED" is your culprit.

HOW TO USE ON RENDER
---------------------
1. Put this file in your backend root (same folder as wsgi.py), e.g. as
   diag_app.py
2. Temporarily change your Render Start Command to:
       gunicorn diag_app:app --bind 0.0.0.0:$PORT --log-level debug
   (Render dashboard -> your service -> Settings -> Start Command)
3. Deploy. Because this app binds the port immediately, Render's port scan
   will succeed right away. Watch the logs for [DIAG] lines.
4. Visit https://<your-render-url>/diag in a browser -- it will show you
   live status of each check as JSON.
5. Whichever check shows "running" forever (never "ok" or "error") is your
   actual blocking step. Fix that specific thing in your real app.
6. Revert the Start Command back to your normal one (gunicorn wsgi:app ...)
   once you've diagnosed the issue. Delete this file or leave it, it's
   harmless either way.

WHY THIS WORKS
--------------
Your real app currently never binds the port at all, because something in
create_app() (Celery/Redis init, DB connect, or rembg model download) hangs
*before* Gunicorn finishes loading the app object. This script flips that:
port binds immediately, and the suspect work happens afterwards in threads,
so you get visibility instead of a silent hang.
"""

import os
import threading
import time
import traceback

from flask import Flask, jsonify

app = Flask(__name__)

# Shared status dict, written by background threads, read by /diag route.
_status = {
    "redis": {"state": "not_started", "detail": None, "seconds": None},
    "celery": {"state": "not_started", "detail": None, "seconds": None},
    "database": {"state": "not_started", "detail": None, "seconds": None},
    "rembg": {"state": "not_started", "detail": None, "seconds": None},
}
_status_lock = threading.Lock()


def _set(key, state, detail=None, seconds=None):
    with _status_lock:
        _status[key] = {"state": state, "detail": detail, "seconds": seconds}
    print(f"[DIAG] {key}: {state} ({detail}) after {seconds}s", flush=True)


def _check_redis():
    """Tests a raw Redis connection using REDIS_URL, with a hard timeout."""
    key = "redis"
    start = time.time()
    _set(key, "running")
    try:
        import redis  # noqa: local import so this thread owns any hang

        url = os.environ.get("REDIS_URL") or os.environ.get("CELERY_BROKER_URL")
        if not url:
            _set(key, "skipped", "REDIS_URL / CELERY_BROKER_URL not set", round(time.time() - start, 2))
            return

        client = redis.from_url(url, socket_connect_timeout=5, socket_timeout=5)
        client.ping()
        _set(key, "ok", f"connected to {url.split('@')[-1]}", round(time.time() - start, 2))
    except Exception as e:
        _set(key, "error", f"{type(e).__name__}: {e}", round(time.time() - start, 2))


def _check_celery():
    """Mimics init_celery(app) -- imports celery and builds an app, with timeout via thread join."""
    key = "celery"
    start = time.time()
    _set(key, "running")
    try:
        from celery import Celery  # noqa

        broker = os.environ.get("CELERY_BROKER_URL") or os.environ.get("REDIS_URL")
        backend = os.environ.get("CELERY_RESULT_BACKEND") or broker

        celery_app = Celery("diag", broker=broker, backend=backend)
        # Force a connection attempt (this is what tends to hang if broker
        # is unreachable, depending on celery/kombu transport settings).
        with celery_app.connection_or_acquire() as conn:
            conn.ensure_connection(max_retries=1, timeout=5)
        _set(key, "ok", "broker connection established", round(time.time() - start, 2))
    except Exception as e:
        _set(key, "error", f"{type(e).__name__}: {e}", round(time.time() - start, 2))


def _check_database():
    """Tests a raw DB connection using DATABASE_URL, with a hard timeout."""
    key = "database"
    start = time.time()
    _set(key, "running")
    try:
        import psycopg

        url = os.environ.get("DATABASE_URL") or os.environ.get("SQLALCHEMY_DATABASE_URI")
        if not url:
            _set(key, "skipped", "DATABASE_URL not set", round(time.time() - start, 2))
            return

        # psycopg3 accepts postgres:// or postgresql:// directly
        conn = psycopg.connect(url, connect_timeout=5)
        conn.close()
        _set(key, "ok", "connected", round(time.time() - start, 2))
    except Exception as e:
        _set(key, "error", f"{type(e).__name__}: {e}", round(time.time() - start, 2))


def _check_rembg():
    """Tests whether rembg's model loading/download is the slow/hanging step."""
    key = "rembg"
    start = time.time()
    _set(key, "running")
    try:
        from rembg import new_session  # this is what triggers model download

        # 'u2net' is rembg's default model; this line is what can hang on a
        # slow/blocked outbound connection while it downloads the model file.
        new_session("u2net")
        _set(key, "ok", "model session created", round(time.time() - start, 2))
    except Exception as e:
        _set(key, "error", f"{type(e).__name__}: {e}", round(time.time() - start, 2))


def _run_with_watchdog(name, fn, timeout=25):
    """Runs fn in a thread; if it doesn't finish within timeout, marks it as
    'still running after timeout' so you know it's the hang culprit even
    though the thread itself is still stuck in the background."""
    t = threading.Thread(target=fn, daemon=True)
    t.start()
    t.join(timeout=timeout)
    if t.is_alive():
        print(
            f"[DIAG] {name}: STILL RUNNING after {timeout}s timeout -- "
            f"this is very likely your blocking step.",
            flush=True,
        )


@app.route("/")
def index():
    return "Diagnostic app is up. Visit /diag for status.", 200


@app.route("/health")
def health():
    # Always returns immediately -- proves the port/web server itself is fine.
    return jsonify({"status": "ok"}), 200


@app.route("/diag")
def diag():
    with _status_lock:
        return jsonify(_status), 200


def _start_background_checks():
    checks = [
        ("redis", _check_redis),
        ("celery", _check_celery),
        ("database", _check_database),
        ("rembg", _check_rembg),
    ]
    for name, fn in checks:
        threading.Thread(
            target=_run_with_watchdog, args=(name, fn), daemon=True
        ).start()


# Kick off checks as soon as the module is imported (i.e. as soon as Gunicorn
# loads this app), but NOT blocking -- so the port still binds instantly.
_start_background_checks()


if __name__ == "__main__":
    # Local run: python diag_app.py
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
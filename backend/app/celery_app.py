from __future__ import annotations

from celery import Celery

celery = Celery("taskhub")


def init_celery(app) -> Celery:
    celery.conf.update(
        broker_url=app.config["CELERY_BROKER_URL"],
        result_backend=app.config["CELERY_RESULT_BACKEND"],
        broker_connection_retry_on_startup=False,
        broker_connection_timeout=3,
        redis_socket_connect_timeout=3,
        redis_socket_timeout=3,
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        worker_prefetch_multiplier=1,
    )

    class FlaskContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = FlaskContextTask
    celery.conf.update(task_ignore_result=False)
    return celery

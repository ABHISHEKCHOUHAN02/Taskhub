from flask import Flask

from .auth.routes import auth_bp
from .config import get_config
from .celery_app import init_celery
from .extensions import db, migrate
from .tasks.routes import tasks_bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(get_config())

    db.init_app(app)
    migrate.init_app(app, db)
    init_celery(app)
    app.register_blueprint(auth_bp)
    app.register_blueprint(tasks_bp)

    from .models import audit_log, generated_image, task, user  # noqa: F401
    from . import jobs  # noqa: F401

    return app

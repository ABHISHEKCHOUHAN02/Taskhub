import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from ..extensions import db
from .enums import UserRole


def enum_values(enum_cls):
    return [member.value for member in enum_cls]


user_role_enum = sa.Enum(
    UserRole,
    name="user_role",
    values_callable=enum_values,
    native_enum=True,
)


class User(db.Model):
    __tablename__ = "users"
    __table_args__ = (
        sa.UniqueConstraint("oauth_provider", "oauth_subject", name="uq_users_oauth_provider_subject"),
    )

    id = db.Column(UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()"))
    email = db.Column(db.Text, nullable=False, unique=True)
    full_name = db.Column(db.Text, nullable=False, default="")
    avatar_url = db.Column(db.Text)
    oauth_provider = db.Column(db.Text, nullable=False)
    oauth_subject = db.Column(db.Text, nullable=False)
    oauth_metadata = db.Column(JSONB, nullable=False, default=dict)
    role = db.Column(user_role_enum, nullable=False, default=UserRole.USER.value)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    last_login_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=sa.text("now()"))
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=sa.text("now()"))

    tasks_created = db.relationship(
        "Task",
        foreign_keys="Task.created_by",
        back_populates="creator",
        lazy="selectin",
    )
    tasks_assigned = db.relationship(
        "Task",
        foreign_keys="Task.assigned_to",
        back_populates="assignee",
        lazy="selectin",
    )
    generated_images = db.relationship(
        "GeneratedImage",
        foreign_keys="GeneratedImage.created_by",
        back_populates="creator",
        lazy="selectin",
    )
    audit_logs = db.relationship(
        "AuditLog",
        foreign_keys="AuditLog.actor_user_id",
        back_populates="actor",
        lazy="selectin",
    )

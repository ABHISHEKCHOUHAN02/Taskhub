import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from ..extensions import db
from .enums import TaskStatus
from .user import User


def enum_values(enum_cls):
    return [member.value for member in enum_cls]


task_status_enum = sa.Enum(
    TaskStatus,
    name="task_status",
    values_callable=enum_values,
    native_enum=True,
)


class Task(db.Model):
    __tablename__ = "tasks"
    __table_args__ = (
        sa.CheckConstraint(
            "(status = 'pending' and assigned_to is null) or (status <> 'pending' and assigned_to is not null)",
            name="tasks_assigned_requires_assignee",
        ),
    )

    id = db.Column(UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()"))
    title = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    status = db.Column(task_status_enum, nullable=False, default=TaskStatus.PENDING.value)
    created_by = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id"), nullable=False)
    assigned_to = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id"))
    product_image_bucket = db.Column(db.Text, nullable=False, default="taskhub-assets")
    product_image_url = db.Column(db.Text, nullable=False)
    product_image_metadata = db.Column(JSONB, nullable=False, default=dict)
    submission_notes = db.Column(db.Text)
    review_notes = db.Column(db.Text)
    due_at = db.Column(db.DateTime(timezone=True))
    assigned_at = db.Column(db.DateTime(timezone=True))
    started_at = db.Column(db.DateTime(timezone=True))
    submitted_at = db.Column(db.DateTime(timezone=True))
    accepted_at = db.Column(db.DateTime(timezone=True))
    revision_requested_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=sa.text("now()"))
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=sa.text("now()"))

    creator = db.relationship(
        User,
        foreign_keys=[created_by],
        back_populates="tasks_created",
        lazy="joined",
    )
    assignee = db.relationship(
        User,
        foreign_keys=[assigned_to],
        back_populates="tasks_assigned",
        lazy="joined",
    )
    generated_images = db.relationship(
        "GeneratedImage",
        back_populates="task",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

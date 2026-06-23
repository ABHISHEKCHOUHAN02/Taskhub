import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from ..extensions import db
from .enums import GeneratedImageType
from .user import User


def enum_values(enum_cls):
    return [member.value for member in enum_cls]


generated_image_type_enum = sa.Enum(
    GeneratedImageType,
    name="generated_image_type",
    values_callable=enum_values,
    native_enum=True,
)


class GeneratedImage(db.Model):
    __tablename__ = "generated_images"
    __table_args__ = (
        sa.CheckConstraint(
            "((image_type in ('model_front', 'model_side', 'model_closeup') and angle is not null) or "
            "(image_type not in ('model_front', 'model_side', 'model_closeup') and angle is null))",
            name="generated_images_angle_check",
        ),
        sa.UniqueConstraint("task_id", "image_type", name="uq_generated_images_task_variant"),
    )

    id = db.Column(UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()"))
    task_id = db.Column(UUID(as_uuid=True), db.ForeignKey("tasks.id"), nullable=False)
    image_type = db.Column(generated_image_type_enum, nullable=False)
    angle = db.Column(db.Text)
    image_bucket = db.Column(db.Text, nullable=False, default="taskhub-assets")
    image_url = db.Column(db.Text, nullable=False)
    prompt_used = db.Column(db.Text, nullable=False, default="")
    metadata_json = db.Column("metadata", JSONB, nullable=False, default=dict)
    is_final = db.Column(db.Boolean, nullable=False, default=False)
    created_by = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=sa.text("now()"))
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=sa.text("now()"))

    task = db.relationship("Task", back_populates="generated_images", lazy="joined")
    creator = db.relationship(
        User,
        foreign_keys=[created_by],
        back_populates="generated_images",
        lazy="joined",
    )

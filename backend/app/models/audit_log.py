from sqlalchemy.dialects.postgresql import JSONB, UUID
import sqlalchemy as sa

from ..extensions import db
from .user import User


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()"))
    actor_user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id", ondelete="SET NULL"))
    entity_type = db.Column(db.Text, nullable=False)
    entity_id = db.Column(UUID(as_uuid=True), nullable=False)
    action = db.Column(db.Text, nullable=False)
    before_data = db.Column(JSONB)
    after_data = db.Column(JSONB)
    metadata_json = db.Column("metadata", JSONB, nullable=False, default=dict)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=sa.text("now()"))

    actor = db.relationship(
        User,
        foreign_keys=[actor_user_id],
        back_populates="audit_logs",
        lazy="joined",
    )

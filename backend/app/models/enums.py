from enum import Enum


class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"


class TaskStatus(str, Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    REVISION_REQUESTED = "revision_requested"


class GeneratedImageType(str, Enum):
    WHITE_BG = "white_bg"
    THEME_MARBLE = "theme_marble"
    THEME_VELVET = "theme_velvet"
    CREATIVE_BEACH = "creative_beach"
    CREATIVE_STUDIO = "creative_studio"
    MODEL_FRONT = "model_front"
    MODEL_SIDE = "model_side"
    MODEL_CLOSEUP = "model_closeup"

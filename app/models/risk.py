"""
Domain-level enums and constants for risks.

These are shared between schemas (API layer) and repositories (DB layer)
so we have a single source of truth for allowed values.
"""
from enum import Enum


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    MITIGATED = "mitigated"
    CLOSED = "closed"


class StepStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class ActionKey(str, Enum):
    VIEW_DETAILS = "view_details"
    MITIGATION_PLAN = "mitigation_plan"
    ASSIGN = "assign"
    TRACK_RISK = "track_risk"


class EventType(str, Enum):
    INITIAL_NOTIFICATION = "initial_notification"
    VIEW_DETAILS = "view_details"
    MITIGATION_PLAN = "mitigation_plan"
    ASSIGN = "assign"
    TRACK_RISK = "track_risk"


class LogStatus(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


# Static action button definitions used in the initial notification payload.
DEFAULT_ACTIONS = [
    {"key": ActionKey.VIEW_DETAILS.value, "label": "View Details"},
    {"key": ActionKey.MITIGATION_PLAN.value, "label": "Mitigation Plan"},
    {"key": ActionKey.ASSIGN.value, "label": "Assign To"},
    {"key": ActionKey.TRACK_RISK.value, "label": "Track This Problem"},
]

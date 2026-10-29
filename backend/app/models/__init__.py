"""集中导入，保证 SQLModel.metadata 在 create_all 前拿到全部表。"""

from app.models.case import Module, TestCase
from app.models.enums import (
    CaseStatus,
    CaseType,
    DraftStatus,
    ExecSource,
    ExecStatus,
    IncidentType,
    PlanStatus,
    Priority,
    Role,
)
from app.models.plan import Execution, TestPlan
from app.models.stability import AiDraft, AutomationRun, StabilityIncident, StabilityRun
from app.models.user import User, utcnow

__all__ = [
    "AiDraft",
    "AutomationRun",
    "CaseStatus",
    "CaseType",
    "DraftStatus",
    "ExecSource",
    "ExecStatus",
    "Execution",
    "IncidentType",
    "Module",
    "PlanStatus",
    "Priority",
    "Role",
    "StabilityIncident",
    "StabilityRun",
    "TestCase",
    "TestPlan",
    "User",
    "utcnow",
]

from enum import StrEnum


class Role(StrEnum):
    """四种角色：访客只读，用于给面试官演示时不担心被改数据。"""

    ADMIN = "admin"
    LEAD = "lead"
    EXECUTOR = "executor"
    VIEWER = "viewer"


class Priority(StrEnum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class CaseType(StrEnum):
    FUNCTION = "function"
    PERFORMANCE = "performance"
    COMPATIBILITY = "compatibility"
    STABILITY = "stability"
    INTERFACE = "interface"


class CaseStatus(StrEnum):
    ACTIVE = "active"
    DRAFT = "draft"
    DEPRECATED = "deprecated"


class PlanStatus(StrEnum):
    DRAFT = "draft"
    RUNNING = "running"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class ExecStatus(StrEnum):
    NOT_RUN = "not_run"
    PASS = "pass"
    FAIL = "fail"
    BLOCKED = "blocked"
    SKIP = "skip"


class ExecSource(StrEnum):
    MANUAL = "manual"
    AUTOMATION = "automation"


class IncidentType(StrEnum):
    CRASH = "crash"
    ANR = "anr"
    HANG = "hang"
    REBOOT = "reboot"
    DISCONNECT = "disconnect"


class DraftStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"

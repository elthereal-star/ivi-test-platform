import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field

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


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page[T](BaseModel):
    total: int
    items: list[T]


class Message(BaseModel):
    detail: str


# ---------------- auth / user ----------------
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserRead"


class UserRead(ORM):
    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: Role
    is_active: bool
    created_at: datetime


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    role: Role = Role.EXECUTOR


class UserUpdate(BaseModel):
    full_name: str | None = None
    role: Role | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserBrief(ORM):
    id: uuid.UUID
    full_name: str
    role: Role


# ---------------- module / case ----------------
class ModuleCreate(BaseModel):
    code: str = Field(max_length=32)
    name: str = Field(max_length=64)
    sort: int = 100


class ModuleRead(ORM):
    id: uuid.UUID
    code: str
    name: str
    sort: int


class CaseStep(BaseModel):
    no: int
    action: str = ""
    expected: str = ""


class CaseBase(BaseModel):
    code: str = Field(max_length=48)
    title: str = Field(max_length=255)
    module_id: uuid.UUID
    priority: Priority = Priority.P2
    case_type: CaseType = CaseType.FUNCTION
    precondition: str = ""
    steps: list[CaseStep] = Field(default_factory=list)
    expected: str = ""
    tags: list[str] = Field(default_factory=list)
    status: CaseStatus = CaseStatus.ACTIVE
    remark: str = ""


class CaseCreate(CaseBase):
    pass


class CaseUpdate(BaseModel):
    title: str | None = None
    module_id: uuid.UUID | None = None
    priority: Priority | None = None
    case_type: CaseType | None = None
    precondition: str | None = None
    steps: list[CaseStep] | None = None
    expected: str | None = None
    tags: list[str] | None = None
    status: CaseStatus | None = None
    remark: str | None = None


class CaseRead(ORM):
    id: uuid.UUID
    code: str
    title: str
    module_id: uuid.UUID
    priority: Priority
    case_type: CaseType
    precondition: str
    steps: list[dict[str, Any]] = Field(default_factory=list)
    expected: str
    tags: list[str] = Field(default_factory=list)
    status: CaseStatus
    remark: str = ""
    updated_at: datetime | None = None


class ImportError_(BaseModel):
    row: int
    reason: str


class ImportResult(BaseModel):
    created: int
    updated: int
    skipped: int
    errors: list[ImportError_] = Field(default_factory=list)


# ---------------- plan / execution ----------------
class PlanCreate(BaseModel):
    code: str = Field(max_length=48)
    name: str = Field(max_length=128)
    fw_version: str = Field(max_length=32)
    device_model: str = "D21x"
    device_sn: str = ""
    remark: str = ""
    case_ids: list[uuid.UUID] = Field(default_factory=list)


class PlanUpdate(BaseModel):
    name: str | None = None
    fw_version: str | None = None
    device_model: str | None = None
    device_sn: str | None = None
    status: PlanStatus | None = None
    remark: str | None = None


class PlanRead(ORM):
    id: uuid.UUID
    code: str
    name: str
    fw_version: str
    device_model: str
    device_sn: str
    status: PlanStatus
    owner_id: uuid.UUID | None = None
    remark: str = ""
    created_at: datetime


class PlanStats(BaseModel):
    total: int
    not_run: int
    passed: int
    failed: int
    blocked: int
    skipped: int
    exec_rate: float
    pass_rate: float
    p0_failed: int


class PlanDetail(PlanRead):
    stats: PlanStats


class ExecUpsert(BaseModel):
    case_id: uuid.UUID
    status: ExecStatus
    duration_s: int | None = None
    actual_result: str = ""
    error_signature: str = ""
    log_excerpt: str = ""


class ExecRead(ORM):
    id: uuid.UUID
    plan_id: uuid.UUID
    case_id: uuid.UUID
    assignee_id: uuid.UUID | None = None
    executor_id: uuid.UUID | None = None
    status: ExecStatus
    source: ExecSource
    duration_s: int | None = None
    actual_result: str = ""
    error_signature: str = ""
    cluster_key: str = ""
    log_excerpt: str = ""
    attempts: int
    executed_at: datetime | None = None


class ExecRow(ExecRead):
    """给撮合页用的宽行：把用例信息一起带上，少发一轮请求。"""

    case_code: str = ""
    case_title: str = ""
    priority: str = ""
    module_name: str = ""


# ---------------- report ----------------
class ModuleStat(BaseModel):
    module_id: uuid.UUID
    module_name: str
    total: int
    executed: int
    passed: int
    failed: int
    pass_rate: float


class PriorityStat(BaseModel):
    priority: str
    total: int
    passed: int
    failed: int
    pass_rate: float


class ClusterStat(BaseModel):
    cluster_key: str
    count: int
    sample: str
    case_codes: list[str] = Field(default_factory=list)
    module_names: list[str] = Field(default_factory=list)


class Dashboard(BaseModel):
    plan_id: uuid.UUID | None = None
    plan_code: str = ""
    fw_version: str = ""
    stats: PlanStats
    by_module: list[ModuleStat] = Field(default_factory=list)
    by_priority: list[PriorityStat] = Field(default_factory=list)
    top_clusters: list[ClusterStat] = Field(default_factory=list)
    trend: list[dict[str, Any]] = Field(default_factory=list)


class CompareCase(BaseModel):
    case_id: uuid.UUID
    case_code: str
    case_title: str
    priority: str
    module_name: str
    base_status: str
    target_status: str


class CompareResult(BaseModel):
    base_plan: PlanRead
    target_plan: PlanRead
    new_fail: list[CompareCase] = Field(default_factory=list)
    fixed: list[CompareCase] = Field(default_factory=list)
    still_fail: list[CompareCase] = Field(default_factory=list)
    new_case: list[CompareCase] = Field(default_factory=list)
    removed: list[CompareCase] = Field(default_factory=list)


# ---------------- stability ----------------
class IncidentCreate(BaseModel):
    incident_type: IncidentType
    module_id: uuid.UUID | None = None
    occurred_at: datetime
    description: str = ""
    log_excerpt: str = ""
    recover_s: int | None = None
    recovered: bool = True


class IncidentRead(ORM):
    id: uuid.UUID
    run_id: uuid.UUID
    incident_type: IncidentType
    module_id: uuid.UUID | None = None
    occurred_at: datetime
    description: str = ""
    log_excerpt: str = ""
    recover_s: int | None = None
    recovered: bool


class StabilityCreate(BaseModel):
    code: str = Field(max_length=48)
    name: str = Field(max_length=128)
    fw_version: str = Field(max_length=32)
    device_sn: str = ""
    start_at: datetime
    end_at: datetime
    planned_hours: float = 24.0
    cycles_done: int = 0
    crash_count: int = 0
    anr_count: int = 0
    hang_count: int = 0
    reboot_count: int = 0
    auto_recover_count: int = 0
    manual_recover_count: int = 0
    notes: str = ""


class StabilityMetrics(BaseModel):
    runtime_hours: float
    total_abnormal: int
    mtbf_hours: float | None = None
    mtbf_cycles: float | None = None
    abnormal_per_hour: float
    recovery_rate: float
    auto_recover_ratio: float
    avg_recover_s: float | None = None


class StabilityRead(ORM):
    id: uuid.UUID
    code: str
    name: str
    fw_version: str
    device_sn: str
    start_at: datetime
    end_at: datetime
    planned_hours: float
    cycles_done: int
    crash_count: int
    anr_count: int
    hang_count: int
    reboot_count: int
    auto_recover_count: int
    manual_recover_count: int
    notes: str = ""


class StabilityDetail(StabilityRead):
    metrics: StabilityMetrics
    by_module: list[dict[str, Any]] = Field(default_factory=list)
    by_type: list[dict[str, Any]] = Field(default_factory=list)
    incidents: list[IncidentRead] = Field(default_factory=list)


# ---------------- automation ----------------
class AutomationResultIn(BaseModel):
    case_code: str
    status: ExecStatus
    duration_s: int | None = None
    message: str = ""
    error_text: str = ""
    log_excerpt: str = ""


class AutomationRunIn(BaseModel):
    plan_code: str
    script_name: str = Field(max_length=128)
    device_sn: str = ""
    started_at: datetime
    finished_at: datetime | None = None
    report_url: str = ""
    results: list[AutomationResultIn] = Field(default_factory=list)


class AutomationRunRead(ORM):
    id: uuid.UUID
    plan_id: uuid.UUID
    script_name: str
    device_sn: str
    started_at: datetime
    finished_at: datetime | None = None
    total: int
    passed: int
    failed: int
    skipped: int
    report_url: str = ""


class AutomationIngestResult(BaseModel):
    run_id: uuid.UUID
    accepted: int
    created: int
    updated: int
    unknown_cases: list[str] = Field(default_factory=list)


# ---------------- ai ----------------
class AiGenerateIn(BaseModel):
    module_id: uuid.UUID
    requirement: str = Field(min_length=5)
    count: int = Field(default=5, ge=1, le=10)
    priority: Priority = Priority.P1


class AiDraftRead(ORM):
    id: uuid.UUID
    module_id: uuid.UUID | None = None
    requirement: str
    count: int
    model_name: str
    fallback: bool
    cases: list[dict[str, Any]] = Field(default_factory=list)
    status: DraftStatus
    accepted_count: int
    created_at: datetime


class AiAcceptIn(BaseModel):
    indices: list[int] = Field(default_factory=list, description="要采纳的草稿下标，空表示全部")


class AiAcceptResult(BaseModel):
    created: int
    case_codes: list[str] = Field(default_factory=list)


Token.model_rebuild()

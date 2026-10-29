import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column, DateTime, Text, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.models.enums import DraftStatus
from app.models.user import utcnow


class StabilityRun(SQLModel, table=True):
    """一轮稳定性压测。指标由 run 时长与异常次数算出，不冗余存储。"""

    __tablename__ = "stability_run"
    __table_args__ = (UniqueConstraint("code", name="uq_stability_code"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    code: str = Field(max_length=48, index=True)
    name: str = Field(max_length=128)
    fw_version: str = Field(max_length=32, index=True)
    device_sn: str = Field(default="", max_length=64)
    start_at: datetime = Field(sa_column=Column(DateTime(timezone=True)))
    end_at: datetime = Field(sa_column=Column(DateTime(timezone=True)))
    planned_hours: float = Field(default=24.0)
    cycles_done: int = Field(default=0)
    crash_count: int = Field(default=0)
    anr_count: int = Field(default=0)
    hang_count: int = Field(default=0)
    reboot_count: int = Field(default=0)
    auto_recover_count: int = Field(default=0)
    manual_recover_count: int = Field(default=0)
    notes: str = Field(default="", sa_column=Column(Text))
    created_by: uuid.UUID | None = Field(default=None, foreign_key="app_user.id")
    created_at: datetime = Field(default_factory=utcnow, sa_column=Column(DateTime(timezone=True)))


class StabilityIncident(SQLModel, table=True):
    """异常明细。压测的价值在这张表：什么时间、什么模块、恢复花了多久。"""

    __tablename__ = "stability_incident"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    run_id: uuid.UUID = Field(foreign_key="stability_run.id", index=True)
    incident_type: str = Field(max_length=16, index=True)
    module_id: uuid.UUID | None = Field(default=None, foreign_key="module.id")
    occurred_at: datetime = Field(sa_column=Column(DateTime(timezone=True)))
    description: str = Field(default="", max_length=255)
    log_excerpt: str = Field(default="", sa_column=Column(Text))
    recover_s: int | None = Field(default=None)
    recovered: bool = Field(default=True)


class AutomationRun(SQLModel, table=True):
    """一次 Appium 脚本批跑。回传后与手工执行进同一张 execution 表。"""

    __tablename__ = "automation_run"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    plan_id: uuid.UUID = Field(foreign_key="test_plan.id", index=True)
    script_name: str = Field(max_length=128)
    device_sn: str = Field(default="", max_length=64)
    started_at: datetime = Field(sa_column=Column(DateTime(timezone=True)))
    finished_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    total: int = Field(default=0)
    passed: int = Field(default=0)
    failed: int = Field(default=0)
    skipped: int = Field(default=0)
    report_url: str = Field(default="", max_length=255)
    created_at: datetime = Field(default_factory=utcnow, sa_column=Column(DateTime(timezone=True)))


class AiDraft(SQLModel, table=True):
    """AI 生成的用例草稿。必须人工审核才能入库，避免大模型幻觉污染用例库。"""

    __tablename__ = "ai_draft"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    module_id: uuid.UUID | None = Field(default=None, foreign_key="module.id")
    requirement: str = Field(sa_column=Column(Text))
    count: int = Field(default=5)
    model_name: str = Field(default="", max_length=64)
    # True 表示走了规则模板降级，而不是真的调了模型
    fallback: bool = Field(default=False)
    cases: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    status: str = Field(default=DraftStatus.PENDING, max_length=16, index=True)
    accepted_count: int = Field(default=0)
    created_by: uuid.UUID | None = Field(default=None, foreign_key="app_user.id")
    created_at: datetime = Field(default_factory=utcnow, sa_column=Column(DateTime(timezone=True)))

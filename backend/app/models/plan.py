import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Text, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.models.enums import ExecSource, ExecStatus, PlanStatus
from app.models.user import utcnow


class TestPlan(SQLModel, table=True):
    """一次回归批次：绑定固件版本 + 设备，是 diff 对比的基准单位。"""

    __tablename__ = "test_plan"
    __table_args__ = (UniqueConstraint("code", name="uq_plan_code"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    code: str = Field(max_length=48, index=True)
    name: str = Field(max_length=128)
    fw_version: str = Field(max_length=32, index=True)
    device_model: str = Field(default="D21x", max_length=64)
    device_sn: str = Field(default="", max_length=64)
    status: str = Field(default=PlanStatus.DRAFT, max_length=16, index=True)
    owner_id: uuid.UUID | None = Field(default=None, foreign_key="app_user.id")
    started_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    finished_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    remark: str = Field(default="", sa_column=Column(Text))
    created_at: datetime = Field(default_factory=utcnow, sa_column=Column(DateTime(timezone=True)))


class Execution(SQLModel, table=True):
    """执行记录。(plan_id, case_id) 唯一，重复执行累加 attempts 并覆盖最新结果。"""

    __tablename__ = "execution"
    __table_args__ = (UniqueConstraint("plan_id", "case_id", name="uq_exec_plan_case"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    plan_id: uuid.UUID = Field(foreign_key="test_plan.id", index=True)
    case_id: uuid.UUID = Field(foreign_key="test_case.id", index=True)
    assignee_id: uuid.UUID | None = Field(default=None, foreign_key="app_user.id")
    executor_id: uuid.UUID | None = Field(default=None, foreign_key="app_user.id")
    status: str = Field(default=ExecStatus.NOT_RUN, max_length=16, index=True)
    source: str = Field(default=ExecSource.MANUAL, max_length=16, index=True)
    duration_s: int | None = Field(default=None)
    actual_result: str = Field(default="", sa_column=Column(Text))
    # 原始报错（人写或脚本日志）
    error_signature: str = Field(default="", sa_column=Column(Text))
    # 归一化后的聚类键，失败聚类按它分组
    cluster_key: str = Field(default="", max_length=255, index=True)
    log_excerpt: str = Field(default="", sa_column=Column(Text))
    automation_run_id: uuid.UUID | None = Field(default=None, foreign_key="automation_run.id")
    attempts: int = Field(default=1)
    executed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    updated_at: datetime = Field(default_factory=utcnow, sa_column=Column(DateTime(timezone=True)))

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column, DateTime, Text, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.models.enums import CaseStatus, CaseType, Priority
from app.models.user import utcnow


class Module(SQLModel, table=True):
    """功能模块（AI 语音 / 导航 / POI / 仪表 ...），看板按它聚合。"""

    __tablename__ = "module"
    __table_args__ = (UniqueConstraint("code", name="uq_module_code"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    code: str = Field(max_length=32, index=True)
    name: str = Field(max_length=64)
    sort: int = Field(default=100)
    created_at: datetime = Field(default_factory=utcnow, sa_column=Column(DateTime(timezone=True)))


class TestCase(SQLModel, table=True):
    __tablename__ = "test_case"
    __table_args__ = (UniqueConstraint("code", name="uq_case_code"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    code: str = Field(max_length=48, index=True)
    title: str = Field(max_length=255)
    module_id: uuid.UUID = Field(foreign_key="module.id", index=True)
    priority: str = Field(default=Priority.P2, max_length=8, index=True)
    case_type: str = Field(default=CaseType.FUNCTION, max_length=16)
    precondition: str = Field(default="", sa_column=Column(Text))
    # [{"no":1,"action":"...","expected":"..."}]，结构化步骤而不是一整坨文本
    steps: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    expected: str = Field(default="", sa_column=Column(Text))
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    status: str = Field(default=CaseStatus.ACTIVE, max_length=16, index=True)
    remark: str = Field(default="", sa_column=Column(Text))
    created_by: uuid.UUID | None = Field(default=None, foreign_key="app_user.id")
    created_at: datetime = Field(default_factory=utcnow, sa_column=Column(DateTime(timezone=True)))
    updated_at: datetime = Field(default_factory=utcnow, sa_column=Column(DateTime(timezone=True)))

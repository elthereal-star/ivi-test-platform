import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime
from sqlmodel import Field, SQLModel

from app.models.enums import Role


def utcnow() -> datetime:
    return datetime.now(UTC)


class User(SQLModel, table=True):
    __tablename__ = "app_user"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    email: str = Field(unique=True, index=True, max_length=255)
    full_name: str = Field(max_length=64)
    hashed_password: str
    # 存字符串而不是 PG 原生 enum：加角色时不用改动数据库类型，迁移成本低
    role: str = Field(default=Role.EXECUTOR, max_length=32)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=utcnow, sa_column=Column(DateTime(timezone=True)))

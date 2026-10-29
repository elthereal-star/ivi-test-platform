from collections.abc import Generator

from sqlalchemy import inspect as sa_inspect
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import settings

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")

# pool_pre_ping：容器里的 Postgres 重启后连接不会变成坏连接，少一类线上事故
engine: Engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    echo=False,
    # SQLite 只用于本地零依赖演示；FastAPI 的线程池会跨线程用同一连接
    connect_args={"check_same_thread": False} if _is_sqlite else {},
)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


def create_db_and_tables() -> None:
    """开发环境直接用 metadata 建表；生产走 Alembic 迁移。"""
    import app.models  # noqa: F401  确保所有模型完成注册

    SQLModel.metadata.create_all(engine)


def table_exists(name: str) -> bool:
    return sa_inspect(engine).has_table(name)

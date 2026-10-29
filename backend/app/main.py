from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import ai, auth, automation, cases, plans, reports, stability
from app.core.config import settings
from app.core.db import create_db_and_tables


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 开发期直接建表；生产用 alembic upgrade head，见 README
    create_db_and_tables()
    if settings.SEED_ON_STARTUP:
        from app.seed import seed_if_empty

        seed_if_empty()
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    description=(
        "车机（IVI）测试数据平台：用例库、测试计划、执行记录、回归对比、"
        "失败聚类、稳定性压测看板、AI 辅助生成用例、自动化结果回传。"
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (auth.router, cases.router, plans.router, reports.router, stability.router, automation.router, ai.router):
    app.include_router(router, prefix=settings.API_V1)


@app.get("/health", tags=["运维"], summary="健康检查")
def health() -> dict[str, str]:
    return {"status": "ok", "project": settings.PROJECT_NAME}


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    return {"docs": "/docs", "api": settings.API_V1}

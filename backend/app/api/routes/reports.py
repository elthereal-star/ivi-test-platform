import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from app.api.deps import require_read
from app.core.db import get_session
from app.models import TestPlan, User
from app.schemas import CompareResult, Dashboard, PlanRead
from app.services import stats as stats_service

router = APIRouter(prefix="/reports", tags=["报表"])


def _latest_plan(session: Session) -> TestPlan | None:
    return session.exec(select(TestPlan).order_by(TestPlan.created_at.desc())).first()


@router.get("/dashboard", response_model=Dashboard, summary="看板聚合")
def dashboard(
    plan_id: uuid.UUID | None = Query(default=None, description="不传则用最近一个批次"),
    session: Session = Depends(get_session),
    _: User = Depends(require_read),
) -> Dashboard:
    if plan_id:
        plan = session.get(TestPlan, plan_id)
        if not plan:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "测试计划不存在")
    else:
        plan = _latest_plan(session)

    if not plan:
        from app.schemas import PlanStats

        empty = PlanStats(
            total=0, not_run=0, passed=0, failed=0, blocked=0, skipped=0,
            exec_rate=0.0, pass_rate=0.0, p0_failed=0,
        )
        return Dashboard(stats=empty)

    return Dashboard(
        plan_id=plan.id,
        plan_code=plan.code,
        fw_version=plan.fw_version,
        stats=stats_service.plan_stats(session, plan.id),
        by_module=stats_service.module_stats(session, plan.id),
        by_priority=stats_service.priority_stats(session, plan.id),
        top_clusters=stats_service.top_clusters(session, plan.id),
        trend=stats_service.trend(session),
    )


@router.get("/compare", response_model=CompareResult, summary="两个批次的回归对比")
def compare(
    base_plan_id: uuid.UUID = Query(description="基准批次（通常是上一版）"),
    target_plan_id: uuid.UUID = Query(description="对比批次（通常是本版）"),
    session: Session = Depends(get_session),
    _: User = Depends(require_read),
) -> CompareResult:
    base = session.get(TestPlan, base_plan_id)
    target = session.get(TestPlan, target_plan_id)
    if not base or not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "批次不存在")
    if base.id == target.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "两个批次不能相同")
    diff = stats_service.compare(session, base_plan_id, target_plan_id)
    return CompareResult(
        base_plan=PlanRead.model_validate(base),
        target_plan=PlanRead.model_validate(target),
        **diff,
    )


@router.get("/clusters", summary="失败聚类明细")
def clusters(
    plan_id: uuid.UUID = Query(...),
    limit: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_session),
    _: User = Depends(require_read),
) -> list[dict]:
    if not session.get(TestPlan, plan_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "测试计划不存在")
    return stats_service.top_clusters(session, plan_id, limit)


@router.get("/trend", summary="批次通过率走势")
def trend(
    limit: int = Query(default=8, ge=2, le=30),
    session: Session = Depends(get_session),
    _: User = Depends(require_read),
) -> list[dict]:
    return stats_service.trend(session, limit)

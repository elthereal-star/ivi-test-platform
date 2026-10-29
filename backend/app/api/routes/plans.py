import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlmodel import Session, select

from app.api.deps import require_exec, require_read, require_write
from app.core.db import get_session
from app.models import (
    ExecSource,
    ExecStatus,
    Execution,
    Module,
    PlanStatus,
    TestCase,
    TestPlan,
    User,
    utcnow,
)
from app.schemas import ExecRead, ExecRow, ExecUpsert, Page, PlanCreate, PlanDetail, PlanRead, PlanUpdate
from app.services import clustering
from app.services import stats as stats_service

router = APIRouter(tags=["测试计划与执行"])


def _plan_or_404(session: Session, plan_id: uuid.UUID) -> TestPlan:
    plan = session.get(TestPlan, plan_id)
    if not plan:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "测试计划不存在")
    return plan


def _detail(session: Session, plan: TestPlan) -> PlanDetail:
    """PlanDetail 的 stats 是计算字段，不能靠 model_validate 从 ORM 直接拿。"""
    return PlanDetail(**PlanRead.model_validate(plan).model_dump(), stats=stats_service.plan_stats(session, plan.id))


def _upsert_execution(
    session: Session,
    plan_id: uuid.UUID,
    payload: ExecUpsert,
    executor_id: uuid.UUID | None,
    source: str = ExecSource.MANUAL,
    automation_run_id: uuid.UUID | None = None,
) -> tuple[Execution, bool]:
    existing = session.exec(
        select(Execution).where(Execution.plan_id == plan_id, Execution.case_id == payload.case_id)
    ).first()

    signature = (payload.error_signature or "").strip()
    cluster_key = clustering.normalize_signature(clustering.split_lines(signature)) if signature else ""

    if existing:
        existing.status = payload.status
        existing.duration_s = payload.duration_s
        existing.actual_result = payload.actual_result
        existing.error_signature = signature
        existing.cluster_key = cluster_key
        existing.log_excerpt = payload.log_excerpt
        existing.executor_id = executor_id or existing.executor_id
        existing.source = source
        existing.automation_run_id = automation_run_id or existing.automation_run_id
        existing.attempts = (existing.attempts or 0) + 1
        existing.executed_at = datetime.now(UTC)
        existing.updated_at = utcnow()
        session.add(existing)
        return existing, False

    if not session.get(TestCase, payload.case_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "用例不存在")
    exec_ = Execution(
        plan_id=plan_id,
        case_id=payload.case_id,
        status=payload.status,
        source=source,
        duration_s=payload.duration_s,
        actual_result=payload.actual_result,
        error_signature=signature,
        cluster_key=cluster_key,
        log_excerpt=payload.log_excerpt,
        executor_id=executor_id,
        automation_run_id=automation_run_id,
        executed_at=datetime.now(UTC),
    )
    session.add(exec_)
    return exec_, True


@router.get("/plans", response_model=Page[PlanDetail], summary="计划列表（含统计）")
def list_plans(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    plan_status: str | None = Query(default=None, alias="status"),
    session: Session = Depends(get_session),
    _: User = Depends(require_read),
) -> Page[PlanDetail]:
    stmt = select(TestPlan)
    count_stmt = select(func.count()).select_from(TestPlan)
    if plan_status:
        stmt = stmt.where(TestPlan.status == plan_status)
        count_stmt = count_stmt.where(TestPlan.status == plan_status)
    total = session.scalar(count_stmt) or 0
    rows = session.exec(stmt.order_by(TestPlan.created_at.desc()).offset((page - 1) * size).limit(size)).all()
    items = [_detail(session, p) for p in rows]
    return Page(total=total, items=items)


@router.post("/plans", response_model=PlanDetail, status_code=201, summary="创建计划并生成待执行清单")
def create_plan(
    payload: PlanCreate,
    session: Session = Depends(get_session),
    user: User = Depends(require_write),
    all_cases: bool = Query(default=False, description="不传 case_ids 时是否纳入全部 active 用例"),
) -> PlanDetail:
    if session.exec(select(TestPlan).where(TestPlan.code == payload.code)).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "计划编号已存在")

    plan = TestPlan(
        code=payload.code,
        name=payload.name,
        fw_version=payload.fw_version,
        device_model=payload.device_model,
        device_sn=payload.device_sn,
        remark=payload.remark,
        owner_id=user.id,
    )
    session.add(plan)
    session.flush()

    if payload.case_ids:
        cases = list(session.exec(select(TestCase).where(TestCase.id.in_(payload.case_ids))).all())
    elif all_cases:
        cases = list(session.exec(select(TestCase).where(TestCase.status == "active")).all())
    else:
        cases = []

    for case in cases:
        session.add(Execution(plan_id=plan.id, case_id=case.id, status=ExecStatus.NOT_RUN))

    session.commit()
    session.refresh(plan)
    return _detail(session, plan)


@router.get("/plans/{plan_id}", response_model=PlanDetail, summary="计划详情")
def get_plan(
    plan_id: uuid.UUID,
    session: Session = Depends(get_session),
    _: User = Depends(require_read),
) -> PlanDetail:
    return _detail(session, _plan_or_404(session, plan_id))


@router.patch("/plans/{plan_id}", response_model=PlanDetail, summary="修改计划")
def update_plan(
    plan_id: uuid.UUID,
    payload: PlanUpdate,
    session: Session = Depends(get_session),
    _: User = Depends(require_write),
) -> PlanDetail:
    plan = _plan_or_404(session, plan_id)
    data = payload.model_dump(exclude_unset=True)
    if data.get("status") == PlanStatus.COMPLETED and not plan.finished_at:
        plan.finished_at = datetime.now(UTC)
    for k, v in data.items():
        setattr(plan, k, v)
    session.add(plan)
    session.commit()
    session.refresh(plan)
    return _detail(session, plan)


@router.post("/plans/{plan_id}/add-cases", response_model=PlanDetail, summary="向计划追加用例")
def add_cases(
    plan_id: uuid.UUID,
    case_ids: list[uuid.UUID],
    session: Session = Depends(get_session),
    _: User = Depends(require_write),
) -> PlanDetail:
    plan = _plan_or_404(session, plan_id)
    existing = set(
        session.exec(select(Execution.case_id).where(Execution.plan_id == plan_id)).all()
    )
    for cid in case_ids:
        if cid in existing:
            continue
        if not session.get(TestCase, cid):
            continue
        session.add(Execution(plan_id=plan_id, case_id=cid, status=ExecStatus.NOT_RUN))
    session.commit()
    return _detail(session, plan)


@router.get("/plans/{plan_id}/executions", response_model=list[ExecRow], summary="执行清单（宽行）")
def list_executions(
    plan_id: uuid.UUID,
    exec_status: str | None = Query(default=None, alias="status"),
    module_id: uuid.UUID | None = None,
    session: Session = Depends(get_session),
    _: User = Depends(require_read),
) -> list[ExecRow]:
    _plan_or_404(session, plan_id)
    stmt = (
        select(Execution, TestCase.code, TestCase.title, TestCase.priority, Module.name)
        .join(TestCase, TestCase.id == Execution.case_id)
        .join(Module, Module.id == TestCase.module_id)
        .where(Execution.plan_id == plan_id)
    )
    if exec_status:
        stmt = stmt.where(Execution.status == exec_status)
    if module_id:
        stmt = stmt.where(TestCase.module_id == module_id)
    rows = session.exec(stmt.order_by(TestCase.priority, TestCase.code)).all()

    out = []
    for exec_, code, title, priority, module_name in rows:
        item = ExecRow.model_validate(exec_)
        item.case_code = code
        item.case_title = title
        item.priority = priority
        item.module_name = module_name
        out.append(item)
    return out


@router.put("/plans/{plan_id}/executions", response_model=ExecRead, summary="录入/更新执行结果")
def upsert_execution(
    plan_id: uuid.UUID,
    payload: ExecUpsert,
    session: Session = Depends(get_session),
    user: User = Depends(require_exec),
) -> Execution:
    plan = _plan_or_404(session, plan_id)
    if plan.status in (PlanStatus.ARCHIVED,):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "已归档的计划不能修改执行结果")
    exec_, _ = _upsert_execution(session, plan_id, payload, executor_id=user.id)
    if plan.status == PlanStatus.DRAFT:
        plan.status = PlanStatus.RUNNING
        session.add(plan)
    session.commit()
    session.refresh(exec_)
    return exec_


@router.patch("/plans/{plan_id}/executions/{case_id}/assign", response_model=ExecRead, summary="分派执行人")
def assign_execution(
    plan_id: uuid.UUID,
    case_id: uuid.UUID,
    assignee_id: uuid.UUID,
    session: Session = Depends(get_session),
    _: User = Depends(require_write),
) -> Execution:
    exec_ = session.exec(
        select(Execution).where(Execution.plan_id == plan_id, Execution.case_id == case_id)
    ).first()
    if not exec_:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "该用例不在此计划中")
    if not session.get(User, assignee_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "执行人不存在")
    exec_.assignee_id = assignee_id
    exec_.updated_at = utcnow()
    session.add(exec_)
    session.commit()
    session.refresh(exec_)
    return exec_


@router.get("/plans/{plan_id}/export", summary="导出执行结果 Excel")
def export_executions(
    plan_id: uuid.UUID,
    session: Session = Depends(get_session),
    _: User = Depends(require_read),
) -> Any:
    from io import BytesIO

    from fastapi import Response
    from openpyxl import Workbook

    plan = _plan_or_404(session, plan_id)
    rows = session.exec(
        select(Execution, TestCase.code, TestCase.title, TestCase.priority, Module.name)
        .join(TestCase, TestCase.id == Execution.case_id)
        .join(Module, Module.id == TestCase.module_id)
        .where(Execution.plan_id == plan_id)
        .order_by(TestCase.code)
    ).all()

    wb = Workbook()
    ws = wb.active
    ws.title = "执行结果"
    ws.append(
        [
            "用例编号", "用例标题", "模块", "优先级", "结果",
            "来源", "耗时(s)", "实际结果", "错误特征", "尝试次数", "执行时间",
        ]
    )
    for e, code, title, pri, mod in rows:
        ws.append(
            [
                code,
                title,
                mod,
                pri,
                e.status,
                e.source,
                e.duration_s,
                e.actual_result,
                e.error_signature,
                e.attempts,
                e.executed_at.strftime("%Y-%m-%d %H:%M") if e.executed_at else "",
            ]
        )
    buf = BytesIO()
    wb.save(buf)
    return Response(
        content=buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{plan.code}-executions.xlsx"'},
    )

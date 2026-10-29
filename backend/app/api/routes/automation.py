import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from app.api.deps import require_read, verify_automation_token
from app.core.db import get_session
from app.models import AutomationRun, ExecSource, ExecStatus, Execution, TestCase, TestPlan, User
from app.schemas import AutomationIngestResult, AutomationRunIn, AutomationRunRead
from app.services import clustering

router = APIRouter(prefix="/automation", tags=["自动化结果回传"])


@router.post(
    "/runs",
    response_model=AutomationIngestResult,
    status_code=201,
    summary="Appium 脚本上报一批执行结果",
    dependencies=[Depends(verify_automation_token)],
)
def ingest_run(payload: AutomationRunIn, session: Session = Depends(get_session)) -> AutomationIngestResult:
    """脚本侧只关心「计划编号 + 用例编号 + 结果」，其余（聚类键、统计）由平台算。"""
    plan = session.exec(select(TestPlan).where(TestPlan.code == payload.plan_code)).first()
    if not plan:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"计划 {payload.plan_code} 不存在")

    run = AutomationRun(
        plan_id=plan.id,
        script_name=payload.script_name,
        device_sn=payload.device_sn,
        started_at=payload.started_at,
        finished_at=payload.finished_at,
        report_url=payload.report_url,
    )
    session.add(run)
    session.flush()

    codes = [r.case_code for r in payload.results]
    cases = {
        c.code: c
        for c in session.exec(select(TestCase).where(TestCase.code.in_(codes))).all()
    } if codes else {}

    existing = {
        e.case_id: e
        for e in session.exec(select(Execution).where(Execution.plan_id == plan.id)).all()
    }

    created = updated = accepted = 0
    unknown: list[str] = []

    for item in payload.results:
        case = cases.get(item.case_code)
        if not case:
            unknown.append(item.case_code)
            continue
        accepted += 1
        signature = (item.error_text or "").strip()
        cluster_key = clustering.normalize_signature(clustering.split_lines(signature)) if signature else ""
        now = datetime.now(UTC)

        exec_ = existing.get(case.id)
        if exec_:
            exec_.status = item.status
            exec_.source = ExecSource.AUTOMATION
            exec_.duration_s = item.duration_s
            exec_.actual_result = item.message
            exec_.error_signature = signature
            exec_.cluster_key = cluster_key
            exec_.log_excerpt = item.log_excerpt
            exec_.automation_run_id = run.id
            exec_.attempts = (exec_.attempts or 0) + 1
            exec_.executed_at = now
            session.add(exec_)
            updated += 1
        else:
            session.add(
                Execution(
                    plan_id=plan.id,
                    case_id=case.id,
                    status=item.status,
                    source=ExecSource.AUTOMATION,
                    duration_s=item.duration_s,
                    actual_result=item.message,
                    error_signature=signature,
                    cluster_key=cluster_key,
                    log_excerpt=item.log_excerpt,
                    automation_run_id=run.id,
                    executed_at=now,
                )
            )
            created += 1

    run.total = accepted
    run.passed = sum(1 for r in payload.results if r.status == ExecStatus.PASS)
    run.failed = sum(1 for r in payload.results if r.status == ExecStatus.FAIL)
    run.skipped = sum(1 for r in payload.results if r.status == ExecStatus.SKIP)
    if plan.status == "draft":
        plan.status = "running"
        session.add(plan)
    session.add(run)
    session.commit()

    return AutomationIngestResult(
        run_id=run.id, accepted=accepted, created=created, updated=updated, unknown_cases=unknown
    )


@router.get("/runs", response_model=list[AutomationRunRead], summary="自动化批跑记录")
def list_runs(
    plan_id: uuid.UUID | None = Query(default=None),
    session: Session = Depends(get_session),
    _: User = Depends(require_read),
) -> list[AutomationRun]:
    stmt = select(AutomationRun).order_by(AutomationRun.started_at.desc()).limit(50)
    if plan_id:
        stmt = stmt.where(AutomationRun.plan_id == plan_id)
    return list(session.exec(stmt).all())

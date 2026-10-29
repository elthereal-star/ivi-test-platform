import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.api.deps import require_read, require_write
from app.core.db import get_session
from app.models import StabilityIncident, StabilityRun, User
from app.schemas import (
    IncidentCreate,
    IncidentRead,
    Message,
    StabilityCreate,
    StabilityDetail,
    StabilityRead,
)
from app.services import stability as st

router = APIRouter(prefix="/stability", tags=["稳定性压测"])


def _detail(session: Session, run: StabilityRun) -> StabilityDetail:
    incidents = list(
        session.exec(
            select(StabilityIncident)
            .where(StabilityIncident.run_id == run.id)
            .order_by(StabilityIncident.occurred_at)
        ).all()
    )
    by_module, by_type = st.breakdown(session, run.id)
    return StabilityDetail(
        **StabilityRead.model_validate(run).model_dump(),
        metrics=st.compute_metrics(run, incidents),
        by_module=by_module,
        by_type=by_type,
        incidents=[IncidentRead.model_validate(i) for i in incidents],
    )


@router.get("/runs", response_model=list[StabilityDetail], summary="压测批次列表")
def list_runs(
    session: Session = Depends(get_session),
    _: User = Depends(require_read),
) -> list[StabilityDetail]:
    runs = session.exec(select(StabilityRun).order_by(StabilityRun.start_at.desc())).all()
    return [_detail(session, r) for r in runs]


@router.post("/runs", response_model=StabilityDetail, status_code=201, summary="新建压测批次")
def create_run(
    payload: StabilityCreate,
    session: Session = Depends(get_session),
    user: User = Depends(require_write),
) -> StabilityDetail:
    if payload.end_at <= payload.start_at:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "结束时间必须晚于开始时间")
    if session.exec(select(StabilityRun).where(StabilityRun.code == payload.code)).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "批次编号已存在")
    run = StabilityRun(**payload.model_dump(), created_by=user.id)
    session.add(run)
    session.commit()
    session.refresh(run)
    return _detail(session, run)


@router.get("/runs/{run_id}", response_model=StabilityDetail, summary="压测详情")
def get_run(
    run_id: uuid.UUID,
    session: Session = Depends(get_session),
    _: User = Depends(require_read),
) -> StabilityDetail:
    run = session.get(StabilityRun, run_id)
    if not run:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "压测批次不存在")
    return _detail(session, run)


@router.post("/runs/{run_id}/incidents", response_model=IncidentRead, status_code=201, summary="追加异常明细")
def add_incident(
    run_id: uuid.UUID,
    payload: IncidentCreate,
    session: Session = Depends(get_session),
    _: User = Depends(require_write),
) -> StabilityIncident:
    run = session.get(StabilityRun, run_id)
    if not run:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "压测批次不存在")
    incident = StabilityIncident(run_id=run_id, **payload.model_dump())
    session.add(incident)
    session.add(run)
    session.commit()
    session.refresh(incident)
    return incident


@router.delete("/runs/{run_id}", response_model=Message, summary="删除压测批次")
def delete_run(
    run_id: uuid.UUID,
    session: Session = Depends(get_session),
    _: User = Depends(require_write),
) -> Message:
    run = session.get(StabilityRun, run_id)
    if not run:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "压测批次不存在")
    for inc in session.exec(select(StabilityIncident).where(StabilityIncident.run_id == run_id)).all():
        session.delete(inc)
    session.delete(run)
    session.commit()
    return Message(detail="已删除")

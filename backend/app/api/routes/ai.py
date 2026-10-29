import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.api.deps import require_read, require_write
from app.core.db import get_session
from app.models import AiDraft, DraftStatus, Module, TestCase, User
from app.schemas import AiAcceptIn, AiAcceptResult, AiDraftRead, AiGenerateIn
from app.services import ai as ai_service

router = APIRouter(prefix="/ai", tags=["AI 辅助"])


@router.post("/generate", response_model=AiDraftRead, status_code=201, summary="按需求生成用例草稿")
def generate(
    payload: AiGenerateIn,
    session: Session = Depends(get_session),
    user: User = Depends(require_write),
) -> AiDraft:
    module = session.get(Module, payload.module_id)
    if not module:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "模块不存在")

    cases, fallback = ai_service.generate(module.name, payload.requirement, payload.count, payload.priority)
    draft = AiDraft(
        module_id=module.id,
        requirement=payload.requirement,
        count=payload.count,
        model_name="rule-template" if fallback else ai_service.settings.AI_MODEL,
        fallback=fallback,
        cases=cases,
        created_by=user.id,
    )
    session.add(draft)
    session.commit()
    session.refresh(draft)
    return draft


@router.get("/drafts", response_model=list[AiDraftRead], summary="草稿列表")
def list_drafts(
    draft_status: str | None = None,
    session: Session = Depends(get_session),
    _: User = Depends(require_read),
) -> list[AiDraft]:
    stmt = select(AiDraft).order_by(AiDraft.created_at.desc()).limit(50)
    if draft_status:
        stmt = stmt.where(AiDraft.status == draft_status)
    return list(session.exec(stmt).all())


def _next_codes(session: Session, prefix: str, n: int) -> list[str]:
    """按模块前缀找当前最大序号往后排，避免与手工建的编号撞车。"""
    rows = session.exec(select(TestCase.code).where(TestCase.code.like(f"{prefix}-%"))).all()
    max_no = 0
    for code in rows:
        m = re.search(rf"^{re.escape(prefix)}-(\d+)$", code)
        if m:
            max_no = max(max_no, int(m.group(1)))
    return [f"{prefix}-{max_no + i:03d}" for i in range(1, n + 1)]


@router.post("/drafts/{draft_id}/accept", response_model=AiAcceptResult, summary="采纳草稿入库")
def accept(
    draft_id: uuid.UUID,
    payload: AiAcceptIn,
    session: Session = Depends(get_session),
    user: User = Depends(require_write),
) -> AiAcceptResult:
    draft = session.get(AiDraft, draft_id)
    if not draft:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "草稿不存在")
    if draft.status == DraftStatus.ACCEPTED:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "该草稿已采纳")

    if payload.indices:
        chosen = [draft.cases[i] for i in payload.indices if 0 <= i < len(draft.cases)]
    else:
        chosen = draft.cases
    if not chosen:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "没有可采纳的用例")

    module = session.get(Module, draft.module_id) if draft.module_id else None
    prefix = module.code if module else "AI"

    # 同一次采纳的用例编号一次性算好再写入，避免循环里重复读到旧值
    codes = _next_codes(session, prefix, len(chosen))
    created: list[str] = []
    for code, item in zip(codes, chosen, strict=True):
        if session.exec(select(TestCase).where(TestCase.code == code)).first():
            continue
        session.add(
            TestCase(
                code=code,
                title=item.get("title", "")[:255],
                module_id=draft.module_id or session.exec(select(Module.id)).first(),
                priority=str(item.get("priority", "P1")).upper(),
                precondition=item.get("precondition", ""),
                steps=item.get("steps", []),
                expected=item.get("expected", ""),
                tags=item.get("tags", []),
                status="draft",
                remark="由 AI 草稿采纳，待复核",
                created_by=user.id,
            )
        )
        created.append(code)

    draft.status = DraftStatus.ACCEPTED
    draft.accepted_count = len(created)
    session.add(draft)
    session.commit()
    return AiAcceptResult(created=len(created), case_codes=created)


@router.post("/drafts/{draft_id}/reject", response_model=AiDraftRead, summary="驳回草稿")
def reject(
    draft_id: uuid.UUID,
    session: Session = Depends(get_session),
    _: User = Depends(require_write),
) -> AiDraft:
    draft = session.get(AiDraft, draft_id)
    if not draft:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "草稿不存在")
    draft.status = DraftStatus.REJECTED
    session.add(draft)
    session.commit()
    session.refresh(draft)
    return draft

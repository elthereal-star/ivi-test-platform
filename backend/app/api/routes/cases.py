import io
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from sqlalchemy import func, or_
from sqlmodel import Session, select

from app.api.deps import require_read, require_write
from app.core.db import get_session
from app.models import Module, TestCase, User, utcnow
from app.schemas import (
    CaseCreate,
    CaseRead,
    CaseUpdate,
    ImportResult,
    ModuleCreate,
    ModuleRead,
    Page,
)
from app.services import excel as excel_service

router = APIRouter(tags=["模块与用例"])


# ---------------- 模块 ----------------
@router.get("/modules", response_model=list[ModuleRead], summary="模块列表")
def list_modules(session: Session = Depends(get_session), _: User = Depends(require_read)) -> list[Module]:
    return list(session.exec(select(Module).order_by(Module.sort, Module.code)).all())


@router.post("/modules", response_model=ModuleRead, status_code=201, summary="新增模块")
def create_module(
    payload: ModuleCreate,
    session: Session = Depends(get_session),
    _: User = Depends(require_write),
) -> Module:
    if session.exec(select(Module).where(Module.code == payload.code.upper())).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "模块编码已存在")
    mod = Module(code=payload.code.upper(), name=payload.name, sort=payload.sort)
    session.add(mod)
    session.commit()
    session.refresh(mod)
    return mod


# ---------------- 用例 ----------------
@router.get("/cases", response_model=Page[CaseRead], summary="用例列表")
def list_cases(
    q: str = Query(default="", description="按编号或标题模糊搜索"),
    module_id: uuid.UUID | None = None,
    priority: str | None = None,
    case_status: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
    session: Session = Depends(get_session),
    _: User = Depends(require_read),
) -> Page[CaseRead]:
    stmt = select(TestCase)
    count_stmt = select(func.count()).select_from(TestCase)
    conds = []
    if q:
        like = f"%{q.strip()}%"
        conds.append(or_(TestCase.code.ilike(like), TestCase.title.ilike(like)))
    if module_id:
        conds.append(TestCase.module_id == module_id)
    if priority:
        conds.append(TestCase.priority == priority)
    if case_status:
        conds.append(TestCase.status == case_status)
    for c in conds:
        stmt = stmt.where(c)
        count_stmt = count_stmt.where(c)

    total = session.scalar(count_stmt) or 0
    rows = session.exec(
        stmt.order_by(TestCase.code).offset((page - 1) * size).limit(size)
    ).all()
    return Page(total=total, items=[CaseRead.model_validate(r) for r in rows])


@router.get("/cases/template", summary="下载导入模板")
def download_template(_: User = Depends(require_read)) -> Response:
    data = excel_service.build_template()
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="ivi-test-case-template.xlsx"'},
    )


@router.get("/cases/export", summary="导出用例为 Excel")
def export_cases(
    module_id: uuid.UUID | None = None,
    session: Session = Depends(get_session),
    _: User = Depends(require_read),
) -> Response:
    from openpyxl import Workbook

    stmt = select(TestCase, Module.code).join(Module, Module.id == TestCase.module_id)
    if module_id:
        stmt = stmt.where(TestCase.module_id == module_id)
    rows = session.exec(stmt.order_by(TestCase.code)).all()

    wb = Workbook()
    ws = wb.active
    ws.title = "用例"
    ws.append(excel_service.HEADERS)
    for case, mod_code in rows:
        steps = case.steps or []
        cells = [case.code, case.title, mod_code, case.priority, case.case_type, case.precondition]
        for i in range(excel_service.STEP_PAIRS):
            s = steps[i] if i < len(steps) else {}
            cells += [s.get("action", ""), s.get("expected", "")]
        cells += [case.expected, ",".join(case.tags or []), case.status, case.remark]
        ws.append(cells)
    buf = io.BytesIO()
    wb.save(buf)
    return Response(
        content=buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="ivi-test-cases.xlsx"'},
    )


@router.post("/cases/import", response_model=ImportResult, summary="Excel 批量导入用例")
def import_cases(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    user: User = Depends(require_write),
) -> ImportResult:
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "只支持 .xlsx 文件")
    try:
        result = excel_service.import_cases(session, file.file.read(), created_by=user)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return ImportResult(**result)


@router.get("/cases/{case_id}", response_model=CaseRead, summary="用例详情")
def get_case(
    case_id: uuid.UUID,
    session: Session = Depends(get_session),
    _: User = Depends(require_read),
) -> TestCase:
    case = session.get(TestCase, case_id)
    if not case:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "用例不存在")
    return case


@router.post("/cases", response_model=CaseRead, status_code=201, summary="新建用例")
def create_case(
    payload: CaseCreate,
    session: Session = Depends(get_session),
    user: User = Depends(require_write),
) -> TestCase:
    if session.exec(select(TestCase).where(TestCase.code == payload.code)).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "用例编号已存在")
    if not session.get(Module, payload.module_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "模块不存在")
    data = payload.model_dump()
    data["steps"] = [s.model_dump() for s in payload.steps]
    case = TestCase(**data, created_by=user.id)
    session.add(case)
    session.commit()
    session.refresh(case)
    return case


@router.patch("/cases/{case_id}", response_model=CaseRead, summary="修改用例")
def update_case(
    case_id: uuid.UUID,
    payload: CaseUpdate,
    session: Session = Depends(get_session),
    _: User = Depends(require_write),
) -> TestCase:
    case = session.get(TestCase, case_id)
    if not case:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "用例不存在")
    data = payload.model_dump(exclude_unset=True)
    if "steps" in data and data["steps"] is not None:
        data["steps"] = [
            s.model_dump() if hasattr(s, "model_dump") else dict(s) for s in data["steps"]
        ]
    for k, v in data.items():
        setattr(case, k, v)
    case.updated_at = utcnow()
    session.add(case)
    session.commit()
    session.refresh(case)
    return case


@router.delete("/cases/{case_id}", response_model=CaseRead, summary="废弃用例（软删除）")
def deprecate_case(
    case_id: uuid.UUID,
    session: Session = Depends(get_session),
    _: User = Depends(require_write),
) -> TestCase:
    """不做物理删除：历史批次里还引用着它，删掉会让回归对比失真。"""
    case = session.get(TestCase, case_id)
    if not case:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "用例不存在")
    case.status = "deprecated"
    case.updated_at = utcnow()
    session.add(case)
    session.commit()
    session.refresh(case)
    return case

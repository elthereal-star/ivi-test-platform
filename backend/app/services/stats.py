"""报表聚合。能下推到 SQL 的都下推，只有聚类和 diff 放 Python（需要分组语义）。"""

import uuid
from typing import Any

from sqlalchemy import case as sa_case
from sqlalchemy import func, select  # 这里故意用 sqlalchemy.select：需要 Row 而不是实体
from sqlmodel import Session

from app.models.case import Module, TestCase
from app.models.enums import ExecStatus, Priority
from app.models.plan import Execution, TestPlan


def _rate(part: int, total: int) -> float:
    return round(part / total * 100, 2) if total else 0.0


def plan_stats(session: Session, plan_id: uuid.UUID) -> dict[str, Any]:
    counts = dict(
        session.exec(
            select(Execution.status, func.count()).where(Execution.plan_id == plan_id).group_by(Execution.status)
        ).all()
    )
    total = sum(counts.values())
    passed = counts.get(ExecStatus.PASS, 0)
    failed = counts.get(ExecStatus.FAIL, 0)
    blocked = counts.get(ExecStatus.BLOCKED, 0)
    skipped = counts.get(ExecStatus.SKIP, 0)
    not_run = counts.get(ExecStatus.NOT_RUN, 0)
    executed = total - not_run
    # 通过率按「已执行且不算跳过」的分母算，避免把未跑的算成失败
    denom = max(executed - skipped, 0)

    p0_failed = session.scalar(
        select(func.count())
        .select_from(Execution)
        .join(TestCase, TestCase.id == Execution.case_id)
        .where(
            Execution.plan_id == plan_id,
            Execution.status == ExecStatus.FAIL,
            TestCase.priority == Priority.P0,
        )
    )

    return {
        "total": total,
        "not_run": not_run,
        "passed": passed,
        "failed": failed,
        "blocked": blocked,
        "skipped": skipped,
        "exec_rate": _rate(executed, total),
        "pass_rate": _rate(passed, denom),
        "p0_failed": p0_failed,
    }


def module_stats(session: Session, plan_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = session.exec(
        select(
            Module.id,
            Module.name,
            func.count().label("total"),
            func.sum(sa_case((Execution.status == ExecStatus.PASS, 1), else_=0)).label("passed"),
            func.sum(sa_case((Execution.status == ExecStatus.FAIL, 1), else_=0)).label("failed"),
            func.sum(sa_case((Execution.status == ExecStatus.NOT_RUN, 1), else_=0)).label("not_run"),
        )
        .select_from(Execution)
        .join(TestCase, TestCase.id == Execution.case_id)
        .join(Module, Module.id == TestCase.module_id)
        .where(Execution.plan_id == plan_id)
        .group_by(Module.id, Module.name, Module.sort)
        .order_by(Module.sort)
    ).all()
    out = []
    for mid, name, total, passed, failed, not_run in rows:
        passed, failed, total = int(passed or 0), int(failed or 0), int(total or 0)
        not_run = int(not_run or 0)
        out.append(
            {
                "module_id": mid,
                "module_name": name,
                "total": total,
                "executed": total - not_run,
                "passed": passed,
                "failed": failed,
                "pass_rate": _rate(passed, total - not_run),
            }
        )
    return out


def priority_stats(session: Session, plan_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = session.exec(
        select(
            TestCase.priority,
            func.count().label("total"),
            func.sum(sa_case((Execution.status == ExecStatus.PASS, 1), else_=0)).label("passed"),
            func.sum(sa_case((Execution.status == ExecStatus.FAIL, 1), else_=0)).label("failed"),
        )
        .select_from(Execution)
        .join(TestCase, TestCase.id == Execution.case_id)
        .where(Execution.plan_id == plan_id)
        .group_by(TestCase.priority)
    ).all()
    order = {p: i for i, p in enumerate(["P0", "P1", "P2", "P3"])}
    out = []
    for pri, total, passed, failed in rows:
        passed, failed, total = int(passed or 0), int(failed or 0), int(total or 0)
        out.append(
            {
                "priority": pri,
                "total": total,
                "passed": passed,
                "failed": failed,
                "pass_rate": _rate(passed, total),
            }
        )
    return sorted(out, key=lambda x: order.get(x["priority"], 9))


def top_clusters(session: Session, plan_id: uuid.UUID, limit: int = 5) -> list[dict[str, Any]]:
    """失败按归一化签名聚类，取数量最多的几簇。"""
    rows = session.exec(
        select(Execution, TestCase.code, Module.name)
        .join(TestCase, TestCase.id == Execution.case_id)
        .join(Module, Module.id == TestCase.module_id)
        .where(
            Execution.plan_id == plan_id,
            Execution.status.in_([ExecStatus.FAIL, ExecStatus.BLOCKED]),
        )
    ).all()

    buckets: dict[str, dict[str, Any]] = {}
    for exec_, code, module_name in rows:
        key = exec_.cluster_key or "未填写错误特征"
        b = buckets.setdefault(
            key, {"cluster_key": key, "count": 0, "sample": "", "case_codes": [], "module_names": []}
        )
        b["count"] += 1
        if not b["sample"]:
            b["sample"] = (exec_.error_signature or exec_.actual_result or "")[:200]
        if code not in b["case_codes"]:
            b["case_codes"].append(code)
        if module_name not in b["module_names"]:
            b["module_names"].append(module_name)

    return sorted(buckets.values(), key=lambda x: -x["count"])[:limit]


def trend(session: Session, limit: int = 8) -> list[dict[str, Any]]:
    """最近若干个批次的通过率走势。"""
    plans = session.exec(
        select(TestPlan.id, TestPlan.code, TestPlan.fw_version).order_by(TestPlan.created_at.desc()).limit(limit)
    ).all()
    out = []
    for pid, code, fw in reversed(plans):
        st = plan_stats(session, pid)
        out.append(
            {
                "plan_code": code,
                "fw_version": fw,
                "pass_rate": st["pass_rate"],
                "exec_rate": st["exec_rate"],
                "failed": st["failed"],
            }
        )
    return out


def compare(session: Session, base_plan_id: uuid.UUID, target_plan_id: uuid.UUID) -> dict[str, Any]:
    """两个批次之间 diff：新增失败 / 已修复 / 仍然失败 / 新增用例 / 已移除用例。"""
    def load(plan_id: uuid.UUID) -> dict[uuid.UUID, tuple[str, str, str, str, str]]:
        rows = session.exec(
            select(Execution.case_id, Execution.status, TestCase.code, TestCase.title, TestCase.priority, Module.name)
            .join(TestCase, TestCase.id == Execution.case_id)
            .join(Module, Module.id == TestCase.module_id)
            .where(Execution.plan_id == plan_id)
        ).all()
        return {r[0]: (r[1], r[2], r[3], r[4], r[5]) for r in rows}

    base, target = load(base_plan_id), load(target_plan_id)
    new_fail, fixed, still_fail, new_case, removed = [], [], [], [], []

    def row(cid: uuid.UUID, info: tuple[str, ...], b: str, t: str) -> dict[str, Any]:
        return {
            "case_id": cid,
            "case_code": info[1],
            "case_title": info[2],
            "priority": info[3],
            "module_name": info[4],
            "base_status": b,
            "target_status": t,
        }

    for cid, tinfo in target.items():
        if cid not in base:
            new_case.append(row(cid, tinfo, "absent", tinfo[0]))
            continue
        binfo = base[cid]
        b, t = binfo[0], tinfo[0]
        if b == ExecStatus.PASS and t == ExecStatus.FAIL:
            new_fail.append(row(cid, tinfo, b, t))
        elif b in (ExecStatus.FAIL, ExecStatus.BLOCKED) and t == ExecStatus.PASS:
            fixed.append(row(cid, tinfo, b, t))
        elif b == ExecStatus.FAIL and t == ExecStatus.FAIL:
            still_fail.append(row(cid, tinfo, b, t))

    for cid, binfo in base.items():
        if cid not in target:
            removed.append(row(cid, binfo, binfo[0], "absent"))

    key = lambda x: (x["priority"], x["case_code"])  # noqa: E731
    return {
        "new_fail": sorted(new_fail, key=key),
        "fixed": sorted(fixed, key=key),
        "still_fail": sorted(still_fail, key=key),
        "new_case": sorted(new_case, key=key),
        "removed": sorted(removed, key=key),
    }

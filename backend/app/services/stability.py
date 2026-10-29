"""稳定性压测指标。

口径写死在这里，避免每份报表算法不一样：
- 运行时长 = end_at - start_at
- 异常总数 = crash + anr + hang + reboot（disconnect 不算，属可恢复链路问题）
- MTBF = 运行时长 / 异常总数
- 恢复率 = 已恢复异常 / 异常总数
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlmodel import Session

from app.models.case import Module
from app.models.stability import StabilityIncident, StabilityRun


def compute_metrics(run: StabilityRun, incidents: list[StabilityIncident] | None = None) -> dict[str, Any]:
    hours = max((run.end_at - run.start_at).total_seconds() / 3600, 0.0)
    abnormal = run.crash_count + run.anr_count + run.hang_count + run.reboot_count
    denom = run.auto_recover_count + run.manual_recover_count

    avg_recover = None
    recovery_rate = 0.0
    if incidents:
        recovered = [i for i in incidents if i.recovered]
        recovery_rate = round(len(recovered) / len(incidents) * 100, 2)
        secs = [i.recover_s for i in incidents if i.recover_s is not None]
        avg_recover = round(sum(secs) / len(secs), 1) if secs else None
    elif denom:
        recovery_rate = round((run.auto_recover_count + run.manual_recover_count) / max(abnormal, 1) * 100, 2)

    return {
        "runtime_hours": round(hours, 2),
        "total_abnormal": abnormal,
        "mtbf_hours": round(hours / abnormal, 2) if abnormal else None,
        "mtbf_cycles": round(run.cycles_done / abnormal, 2) if abnormal else None,
        "abnormal_per_hour": round(abnormal / hours, 3) if hours else 0.0,
        "recovery_rate": min(recovery_rate, 100.0),
        "auto_recover_ratio": round(run.auto_recover_count / denom * 100, 2) if denom else 0.0,
        "avg_recover_s": avg_recover,
    }


def breakdown(session: Session, run_id: uuid.UUID) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_module = session.exec(
        select(Module.name, func.count())
        .select_from(StabilityIncident)
        .join(Module, Module.id == StabilityIncident.module_id, isouter=True)
        .where(StabilityIncident.run_id == run_id)
        .group_by(Module.name)
        .order_by(func.count().desc())
    ).all()
    by_type = session.exec(
        select(StabilityIncident.incident_type, func.count())
        .where(StabilityIncident.run_id == run_id)
        .group_by(StabilityIncident.incident_type)
        .order_by(func.count().desc())
    ).all()
    return (
        [{"module_name": name or "未标注", "count": int(c)} for name, c in by_module],
        [{"incident_type": t, "count": int(c)} for t, c in by_type],
    )


def fmt_dt(v: datetime) -> str:
    return v.strftime("%Y-%m-%d %H:%M")

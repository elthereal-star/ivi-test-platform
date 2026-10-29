"""AI 生成用例草稿。

两个刻意的设计：
1. 只产出「草稿」，必须人工审核后入库。大模型写出来的用例看着通顺但前置条件经常缺，
   直接进用例库等于给自己埋债。
2. 没配 API Key 时走规则模板降级，而不是报错。这样同事拉下代码不配 Key 也能把流程跑通，
   也便于面试现场断网演示。
"""

import json
import logging
import re
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是资深车机（IVI）测试工程师。请根据给定的功能模块和需求描述，输出测试用例草稿。

要求：
1. 严格输出 JSON 数组，不要 Markdown 代码块，不要解释文字。
2. 每个元素字段：title(字符串)、priority(P0/P1/P2)、precondition(字符串)、
   steps(数组，元素为 {"no":序号,"action":"操作","expected":"预期"})、expected(字符串)、tags(字符串数组)。
3. 用例要覆盖：主流程、边界值、异常/中断、恢复能力。不要写重复用例。
4. 步骤要具体到可手工执行（说什么话、点什么按钮、看哪个区域），不要写「测试导航功能」这种空话。
"""


def _strip_code_fence(text: str) -> str:
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t)
    return t.strip()


def _normalize_cases(raw: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in raw[:limit]:
        if not isinstance(item, dict) or not item.get("title"):
            continue
        steps = []
        for i, s in enumerate(item.get("steps") or [], start=1):
            if isinstance(s, dict):
                steps.append(
                    {
                        "no": i,
                        "action": str(s.get("action", "")).strip(),
                        "expected": str(s.get("expected", "")).strip(),
                    }
                )
            elif isinstance(s, str):
                steps.append({"no": i, "action": s.strip(), "expected": ""})
        out.append(
            {
                "title": str(item["title"]).strip()[:255],
                "priority": str(item.get("priority", "P1")).upper()[:2] or "P1",
                "precondition": str(item.get("precondition", "")).strip(),
                "steps": steps,
                "expected": str(item.get("expected", "")).strip(),
                "tags": [str(t) for t in (item.get("tags") or [])][:6],
            }
        )
    return out


def call_llm(module_name: str, requirement: str, count: int, priority: str) -> list[dict[str, Any]] | None:
    if not (settings.AI_BASE_URL and settings.AI_API_KEY):
        return None
    url = settings.AI_BASE_URL.rstrip("/") + "/chat/completions"
    payload = {
        "model": settings.AI_MODEL,
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"模块：{module_name}\n需求：{requirement}\n"
                    f"请生成 {count} 条用例，优先级以 {priority} 为主。"
                    '以 {"cases": [...]} 的 JSON 对象返回。'
                ),
            },
        ],
    }
    try:
        with httpx.Client(timeout=settings.AI_TIMEOUT_S) as client:
            resp = client.post(url, json=payload, headers={"Authorization": f"Bearer {settings.AI_API_KEY}"})
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
        data = json.loads(_strip_code_fence(content))
        raw = data.get("cases") if isinstance(data, dict) else data
        cases = _normalize_cases(raw or [], count)
        return cases or None
    except Exception as exc:  # 网络/额度/格式问题都降级，不让主流程挂
        logger.warning("LLM 生成失败，降级为模板：%s", exc)
        return None


# ---------------- 规则模板降级 ----------------

_BOUNDARY_HINTS = {
    "弱网": ("弱网环境", "将网络限速至 200kbps 或直接断网"),
    "断网": ("断网环境", "关闭车机数据网络"),
    "重启": ("重启场景", "执行过程中强制重启车机"),
    "并发": ("并发场景", "同时触发语音与导航两个入口"),
    "超长": ("边界值", "输入超出长度上限的字符串"),
    "方言": ("方言/口音", "使用带方言口音的口述指令"),
    "无网": ("无网环境", "断开所有网络连接"),
    "夜间": ("夜间模式", "切换至夜间主题后执行"),
}


def _pick_scenarios(requirement: str) -> list[tuple[str, str]]:
    hits = [(name, hint) for kw, (name, hint) in _BOUNDARY_HINTS.items() if kw in requirement]
    return hits[:2]


def fallback_cases(module_name: str, requirement: str, count: int, priority: str) -> list[dict[str, Any]]:
    """按「主流程 / 边界 / 异常中断 / 恢复」四类骨架填充，保证每条都能手工执行。"""
    short = requirement.strip().replace("\n", " ")[:40]
    scenarios = _pick_scenarios(requirement)
    base = [
        {
            "title": f"{module_name}：{short} 主流程验证",
            "priority": priority,
            "precondition": f"车机正常启动，{module_name}服务可用，网络正常",
            "steps": [
                {"no": 1, "action": f"进入{module_name}入口，触发「{short}」", "expected": "界面正常响应，无卡顿"},
                {"no": 2, "action": "按需求描述的预期路径完成操作", "expected": "结果与需求一致"},
                {"no": 3, "action": "退出该界面后再次进入", "expected": "状态正确保留或按设计重置"},
            ],
            "expected": f"「{short}」主流程功能符合需求定义",
            "tags": [module_name, "主流程"],
        },
        {
            "title": f"{module_name}：{short} 连续快速操作不崩溃",
            "priority": "P1",
            "precondition": "车机已开机，模块已就绪",
            "steps": [
                {"no": 1, "action": "连续 10 次快速点击触发入口", "expected": "无 ANR、无重复弹窗、无崩溃"},
                {"no": 2, "action": "在响应未返回时再次触发同一操作", "expected": "有防重复处理或给出明确提示"},
                {"no": 3, "action": "查看 logcat", "expected": "无 FATAL EXCEPTION 记录"},
            ],
            "expected": "高频操作下模块稳定，不出现 ANR/崩溃",
            "tags": [module_name, "稳定性"],
        },
        {
            "title": f"{module_name}：{short} 执行过程中来电打断后恢复",
            "priority": "P1",
            "precondition": "车机已连接蓝牙手机，可正常呼入",
            "steps": [
                {"no": 1, "action": f"触发「{short}」", "expected": "功能正常进行"},
                {"no": 2, "action": "此时用手机呼入并接听", "expected": "通话界面正常弹出，原功能按设计挂起"},
                {"no": 3, "action": "挂断电话", "expected": "回到原界面，功能可继续或被明确终止"},
            ],
            "expected": "跨模块打断后状态一致，无残留弹窗或黑屏",
            "tags": [module_name, "中断恢复"],
        },
        {
            "title": f"{module_name}：{short} 结果为空/无匹配时的提示",
            "priority": "P2",
            "precondition": "车机网络正常，模块可正常访问",
            "steps": [
                {"no": 1, "action": "构造无匹配结果的条件触发操作", "expected": "给出明确的空态提示，不显示空白页"},
                {"no": 2, "action": "在空态页面等待 30 秒", "expected": "无自动重试风暴，无内存持续增长"},
            ],
            "expected": "空态提示清晰，界面不出现无响应",
            "tags": [module_name, "异常场景"],
        },
        {
            "title": f"{module_name}：{short} 切换语言/主题后表现一致",
            "priority": "P2",
            "precondition": "系统支持中英文与日夜主题切换",
            "steps": [
                {"no": 1, "action": f"在中文+日间主题下执行「{short}」", "expected": "文案与配色正常"},
                {
                    "no": 2,
                    "action": "切换为英文+夜间主题后重复执行",
                    "expected": "文案无截断、无中文残留，配色符合夜间规范",
                },
            ],
            "expected": "多语言与主题切换下显示正确",
            "tags": [module_name, "兼容性"],
        },
    ]

    for name, hint in scenarios:
        base.insert(
            1,
            {
                "title": f"{module_name}：{short} 在{name}下的表现",
                "priority": "P1",
                "precondition": f"{hint}，其余环境正常",
                "steps": [
                    {"no": 1, "action": f"构造{name}条件：{hint}", "expected": "条件生效（可通过状态栏确认）"},
                    {"no": 2, "action": f"执行「{short}」", "expected": "有明确提示或降级方案，不静默失败"},
                    {"no": 3, "action": f"恢复{name}条件后重试", "expected": "功能自动恢复或提示用户重试"},
                ],
                "expected": f"{name}下功能有明确反馈，恢复后可用",
                "tags": [module_name, name],
            },
        )
    return base[:count]


def generate(module_name: str, requirement: str, count: int, priority: str) -> tuple[list[dict[str, Any]], bool]:
    cases = call_llm(module_name, requirement, count, priority)
    if cases:
        return cases, False
    return fallback_cases(module_name, requirement, count, priority), True

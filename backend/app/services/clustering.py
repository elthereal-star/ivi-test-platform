"""失败聚类：把「看起来一样」的报错归到同一簇。

车机测试里的失败日志通常是这种形态（手工填的、Appium 抛的、logcat 抓的）：

    java.lang.NullPointerException: Cannot invoke "String.length()" at
    MapService.getPoiList(MapService.java:137)  device=SN2026000123  t=2026-10-29 19:54:12.345

同一根因在不同用例、不同时间跑出来，只有设备号/时间戳/行号会变。直接按字符串分组等于没分，
所以先做归一化：抹掉时间、UUID、IP、路径、十六进制、连续数字，再压缩空白，最后截断。
"""

import re

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I), "<uuid>"),
    (re.compile(r"\d{4}[-/]\d{2}[-/]\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d{3})?"), "<ts>"),
    (re.compile(r"\d{2}:\d{2}:\d{2}(?:[.,]\d{3})?"), "<time>"),
    (re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?\b"), "<ip>"),
    (re.compile(r"0x[0-9a-f]+", re.I), "<hex>"),
    (re.compile(r"\b[0-9a-f]{16,}\b", re.I), "<hash>"),
    (re.compile(r"(?:[A-Za-z]:\\|/)[\w./\\-]{3,}"), "<path>"),
    (re.compile(r"\b\d+\.\d+\b"), "<num>"),
    (re.compile(r"\b\d+\b"), "<n>"),
    (re.compile(r"\s+"), " "),
]


def normalize_signature(text: str, max_len: int = 200) -> str:
    """返回归一化后的聚类键；空输入返回空串（空签名不参与聚类）。"""
    if not text or not text.strip():
        return ""
    s = text.strip().lower()
    # 堆栈帧里的类名/行号对「是不是同一个 bug」没有信息量，反而会把同根因拆成多簇
    s = re.split(r"\s+at\s+(?:com|android|java|org|kotlin)\.", s, maxsplit=1)[0]
    for pattern, repl in _PATTERNS:
        s = pattern.sub(repl, s)
    return s.strip(" .;:-,|")[:max_len]


def split_lines(text: str, limit: int = 3) -> str:
    """只取报错的前几行做签名，避免整段 logcat 进聚类键。"""
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    return " | ".join(lines[:limit])

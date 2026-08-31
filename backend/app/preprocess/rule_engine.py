"""Rule-based preprocess engine: polyphone detection + symbol detection.

Fast, deterministic, zero-cost. Flags text that needs LLM intervention.
"""

import re
from dataclasses import dataclass, field

POLYPHONE_DICT = {
    "银行": "yín háng", "行走": "xíng zǒu", "音乐": "yīn yuè",
    "快乐": "kuài lè", "成长": "chéng zhǎng", "长度": "cháng dù",
    "重要": "zhòng yào", "重复": "chóng fù", "调整": "tiáo zhěng",
    "调查": "diào chá",
}

MATH_CHEM_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"∂"), "partial_differential"),
    (re.compile(r"∫"), "integral"),
    (re.compile(r"∑"), "summation"),
    (re.compile(r"√"), "square_root"),
    (re.compile(r"∞"), "infinity"),
    (re.compile(r"≈"), "approximately_equal"),
    # Chemical formula: uppercase-starting element symbols with optional
    # Unicode subscript digits (₀-₉) or ASCII digits
    (re.compile(r"[A-Z][a-z]?[₀-₉\d]*(?:[A-Z][a-z]?[₀-₉\d]*)+"), "chemical_formula"),
]

# P2-9：确定性本地替换表——LLM 失败时的真实兜底，而不是原样输出。
# 数学符号读音与常见化学式名称是客观事实，无需语义理解即可正确转写。
SYMBOL_READINGS = {
    "∂": "偏导数", "∫": "积分", "∑": "求和",
    "√": "根号", "∞": "无穷大", "≈": "约等于",
}

COMMON_CHEMICAL_NAMES = {
    "H₂O": "水", "H₂SO₄": "硫酸", "NaCl": "氯化钠",
    "CO₂": "二氧化碳", "O₂": "氧气", "H₂": "氢气",
}


@dataclass
class PreprocessResult:
    processed_text: str
    needs_llm: bool = False
    detected_issues: list[str] = field(default_factory=list)
    substitutions: list[tuple[str, str]] = field(default_factory=list)


def rule_preprocess(text: str) -> PreprocessResult:
    result = PreprocessResult(processed_text=text)

    for word, _ in POLYPHONE_DICT.items():
        if word in text:
            result.detected_issues.append(f"polyphone:{word}")
            result.needs_llm = True

    for pattern, label in MATH_CHEM_PATTERNS:
        if pattern.findall(text):
            result.detected_issues.append(f"symbol:{label}")
            result.needs_llm = True

    return result


def rule_fallback(text: str) -> str:
    """LLM 不可用/失败时的确定性兜底（P2-9）。

    数学符号读音与常见化学式名称可本地客观转写；多音字消歧需要上下文
    语义，本地无法确定性替换——兜底时保留原文（可能读错音，但文本正确），
    比强行替换成固定读音更不易出错。
    """
    for formula, name in COMMON_CHEMICAL_NAMES.items():
        text = text.replace(formula, name)
    for symbol, reading in SYMBOL_READINGS.items():
        text = text.replace(symbol, reading)
    return text

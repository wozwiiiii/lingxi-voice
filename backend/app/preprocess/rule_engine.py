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

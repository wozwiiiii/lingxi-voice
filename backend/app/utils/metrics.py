"""Prometheus 指标定义与埋点助手。

生产级 AI 应用可观测性（对应架构文章「Token/延迟/质量全方位监控」）：
灵犀语伴之前零埋点，出故障只能靠猜。本模块集中定义所有业务指标，
在 provider 调用、LLM 预处理、课件合成、熔断等关键链路埋点。

指标分四类：
- 调用量：TTS 合成、LLM 预处理、课件页合成的次数
- 延迟：TTS 合成、LLM 调用的耗时（Histogram）
- 熔断：状态转换、失败计数
- 成本：合成字符数、token 量（近似）

prometheus_client 已在 requirements（0.21.1），此前零引用属死依赖，现激活。
"""

import time
from contextlib import asynccontextmanager

from prometheus_client import Counter, Histogram

# ---- TTS 合成 ----
TTS_SYNTHESIS_TOTAL = Counter(
    "lingxi_tts_synthesis_total",
    "TTS 合成调用总数（按 provider 与结果）",
    ["provider", "outcome"],  # outcome: success / error
)
TTS_SYNTHESIS_DURATION = Histogram(
    "lingxi_tts_synthesis_duration_seconds",
    "TTS 合成耗时（秒）",
    ["provider"],
)
TTS_CHARACTERS_TOTAL = Counter(
    "lingxi_tts_characters_total",
    "合成文本总字符数（成本估算依据）",
    ["provider"],
)

# ---- LLM 预处理 ----
LLM_CALL_TOTAL = Counter(
    "lingxi_llm_call_total",
    "LLM 预处理调用总数（按结果）",
    ["outcome"],  # success / fallback
)
LLM_CALL_DURATION = Histogram(
    "lingxi_llm_call_duration_seconds",
    "LLM 预处理耗时（秒）",
)
LLM_RULE_HIT_TOTAL = Counter(
    "lingxi_llm_rule_hit_total",
    "规则引擎命中次数（needs_llm 判定），用于衡量 LLM 触发率",
    ["needs_llm"],  # true / false
)

# ---- 课件合成 ----
COURSEWARE_SLIDE_TOTAL = Counter(
    "lingxi_courseware_slide_total",
    "课件页合成总数（按结果）",
    ["outcome"],  # completed / failed / timeout
)

# ---- 熔断器 ----
CIRCUIT_STATE_TRANSITIONS = Counter(
    "lingxi_circuit_state_transitions",
    "熔断器状态转换次数",
    ["provider", "to_state"],
)
CIRCUIT_REJECTED_TOTAL = Counter(
    "lingxi_circuit_rejected_total",
    "因熔断打开而拒绝的请求数",
    ["provider"],
)


@asynccontextmanager
async def observe_tts(provider: str):
    """埋点 TTS 合成：记录耗时与成败。用法：

        async with observe_tts(provider) as outcome:
            result = await provider.synthesize(...)
            outcome["success"] = True
    """
    start = time.monotonic()
    outcome = {"success": False}
    try:
        yield outcome
    finally:
        TTS_SYNTHESIS_DURATION.labels(provider).observe(time.monotonic() - start)
        TTS_SYNTHESIS_TOTAL.labels(
            provider, "success" if outcome["success"] else "error"
        ).inc()


@asynccontextmanager
async def observe_llm():
    """埋点 LLM 调用：记录耗时。用法：

        async with observe_llm() as outcome:
            result = await llm_call(...)
            outcome["success"] = True
    """
    start = time.monotonic()
    outcome = {"success": False}
    try:
        yield outcome
    finally:
        LLM_CALL_DURATION.observe(time.monotonic() - start)
        LLM_CALL_TOTAL.labels("success" if outcome["success"] else "fallback").inc()

"""Circuit breaker pattern for TTS providers.

State is stored in Redis so all API instances share the same circuit state.
Uses a simple state machine: CLOSED → OPEN → HALF_OPEN → CLOSED

半开探测（half-open probe）：
    熔断器进入 HALF_OPEN 后，若直接全量放行，一次瞬时抖动就会让所有请求
    重新压向上游，把「快速失败」又变回「慢失败雪崩」。生产级做法是只放行
    一个试探请求：成功 → CLOSED（恢复），失败 → 重新 OPEN（继续熔断），
    其余请求在试探期间一律拒绝/降级。

    用 Redis 的 SET NX 做原子占位符：HALF_OPEN 下并发到达的多个请求里，
    只有抢到占位符的那个获得「试探权」，其余拿到 False。占位符带短 TTL，
    即使试探请求崩溃（没来得及 record_success/record_failure），占位符也
    会自动过期，下一个请求能重新抢到试探权，熔断器不会卡死在 HALF_OPEN。
"""

import time
from enum import Enum

from app.utils.metrics import CIRCUIT_STATE_TRANSITIONS
from app.utils.redis_client import get_redis


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(Exception):
    """Raised when a provider is called while its circuit is OPEN."""


class CircuitBreaker:
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 30,
        probe_ttl: int = 15,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        # 试探占位符的存活时间：覆盖一次 TTS 调用的合理耗时，同时保证
        # 试探请求崩溃后能自动恢复试探权
        self.probe_ttl = probe_ttl

    def _key(self, suffix: str = "") -> str:
        base = f"provider:circuit:{self.name}"
        return f"{base}:{suffix}" if suffix else base

    def _probe_key(self) -> str:
        return self._key("probe")

    async def get_state(self) -> CircuitState:
        redis = await get_redis()
        state_val = await redis.get(self._key())
        if state_val is None:
            return CircuitState.CLOSED
        state_str, timestamp_str = state_val.split(":", 1)
        state = CircuitState(state_str)
        if state == CircuitState.OPEN:
            if time.time() - float(timestamp_str) >= self.recovery_timeout:
                await self._transition_to(CircuitState.HALF_OPEN)
                return CircuitState.HALF_OPEN
        return state

    async def try_acquire_probe(self) -> bool:
        """HALF_OPEN 下抢试探权：抢到 True（放行这一个请求），否则 False（拒绝）。

        用 SET NX EX 保证原子性——多实例并发下只有一个请求能拿到试探权。
        调用方必须保证：抢到 True 的请求无论成败都要 record_success /
        record_failure，以驱动熔断器回到 CLOSED 或重新 OPEN。
        """
        redis = await get_redis()
        acquired = await redis.set(
            self._probe_key(), "1", nx=True, ex=self.probe_ttl
        )
        return bool(acquired)

    async def record_success(self) -> None:
        redis = await get_redis()
        await redis.delete(self._key())
        await redis.delete(self._key("failures"))
        await redis.delete(self._probe_key())

    async def record_failure(self) -> None:
        redis = await get_redis()
        # 半开试探失败：HALF_OPEN 下的这一次失败本身就足以判定「还没恢复」，
        # 应立即重新 OPEN，而不是再累计 failure_threshold 次——否则试探请求
        # 会被放行 failure_threshold 次，把半开探测退化成「半开全量放行」。
        current_state = await self.get_state()
        if current_state == CircuitState.HALF_OPEN:
            await self._transition_to(CircuitState.OPEN)
            await redis.delete(self._probe_key())
            return

        current = await redis.incr(self._key("failures"))
        # 失败计数器加 TTL：窗口外的零星失败不应跨天累积触发熔断
        await redis.expire(self._key("failures"), self.recovery_timeout * 2)
        if current >= self.failure_threshold:
            await self._transition_to(CircuitState.OPEN)

    async def _transition_to(self, state: CircuitState) -> None:
        redis = await get_redis()
        await redis.set(self._key(), f"{state.value}:{time.time()}")
        CIRCUIT_STATE_TRANSITIONS.labels(self.name, state.value).inc()
        if state == CircuitState.CLOSED:
            await redis.delete(self._key("failures"))
            await redis.delete(self._probe_key())

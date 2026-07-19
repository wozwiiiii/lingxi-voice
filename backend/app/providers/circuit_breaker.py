"""Circuit breaker pattern for TTS providers.

State is stored in Redis so all API instances share the same circuit state.
Uses a simple state machine: CLOSED → OPEN → HALF_OPEN → CLOSED
"""

import time
from enum import Enum

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
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

    def _key(self, suffix: str = "") -> str:
        base = f"provider:circuit:{self.name}"
        return f"{base}:{suffix}" if suffix else base

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

    async def record_success(self) -> None:
        redis = await get_redis()
        await redis.delete(self._key())
        await redis.delete(self._key("failures"))

    async def record_failure(self) -> None:
        redis = await get_redis()
        current = await redis.incr(self._key("failures"))
        if current >= self.failure_threshold:
            await self._transition_to(CircuitState.OPEN)

    async def _transition_to(self, state: CircuitState) -> None:
        redis = await get_redis()
        await redis.set(self._key(), f"{state.value}:{time.time()}")
        if state == CircuitState.CLOSED:
            await redis.delete(self._key("failures"))

"""TDD tests for CircuitBreaker state machine.

Tests cover: CLOSED→OPEN→HALF_OPEN→CLOSED transitions,
failure counting, success reset, and key isolation."""

import fakeredis.aioredis
import pytest

from app.providers.circuit_breaker import CircuitBreaker, CircuitState
from app.utils import redis_client as redis_module


@pytest.fixture(autouse=True)
def _mock_redis():
    """Replace global Redis with fakeredis so all circuit breaker tests run offline."""
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    original = redis_module.redis_client
    redis_module.redis_client = fake
    yield
    redis_module.redis_client = original


@pytest.fixture
def cb():
    return CircuitBreaker(name="test_cb", failure_threshold=3, recovery_timeout=1)


class TestInitialState:
    def test_key_format(self, cb):
        assert cb._key() == "provider:circuit:test_cb"

    @pytest.mark.asyncio
    async def test_get_state_returns_closed_initially(self, cb):
        assert await cb.get_state() == CircuitState.CLOSED


class TestFailureCounting:
    @pytest.mark.asyncio
    async def test_single_failure_does_not_open(self, cb):
        await cb.record_failure()
        assert await cb.get_state() == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_threshold_failures_opens_circuit(self, cb):
        for _ in range(3):
            await cb.record_failure()
        assert await cb.get_state() == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_two_failures_stays_closed(self, cb):
        await cb.record_failure()
        await cb.record_failure()
        assert await cb.get_state() == CircuitState.CLOSED


class TestSuccessReset:
    @pytest.mark.asyncio
    async def test_success_after_failures_resets_counter(self, cb):
        await cb.record_failure()
        await cb.record_failure()
        await cb.record_success()
        await cb.record_failure()
        assert await cb.get_state() == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_success_resets_fully(self, cb):
        await cb.record_failure()
        await cb.record_failure()
        await cb.record_success()
        await cb.record_failure()
        await cb.record_failure()
        assert await cb.get_state() == CircuitState.CLOSED


class TestHalfOpenTransition:
    @pytest.mark.asyncio
    async def test_half_open_probe_success_closes(self, cb):
        for _ in range(3):
            await cb.record_failure()
        assert await cb.get_state() == CircuitState.OPEN
        # Force half-open (simulating recovery timeout)
        await cb._transition_to(CircuitState.HALF_OPEN)
        assert await cb.get_state() == CircuitState.HALF_OPEN
        await cb.record_success()
        assert await cb.get_state() == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_half_open_probe_failure_reopens(self, cb):
        for _ in range(3):
            await cb.record_failure()
        await cb._transition_to(CircuitState.HALF_OPEN)
        await cb.record_failure()
        assert await cb.get_state() == CircuitState.OPEN


class TestCircuitKeyIsolation:
    @pytest.mark.asyncio
    async def test_different_names_isolated(self, cb):
        cb2 = CircuitBreaker(name="other_cb", failure_threshold=2)
        for _ in range(3):
            await cb.record_failure()
        assert await cb.get_state() == CircuitState.OPEN
        assert await cb2.get_state() == CircuitState.CLOSED

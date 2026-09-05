"""Provider chain: selects the first non-open provider in the configured chain.

TTS_PROVIDER_CHAIN env var defines the preference order, e.g.:
  "local:cosyvoice2,cloud:siliconflow"
"""

import logging

from app.config import settings
from app.providers.base import TTSProvider
from app.providers.circuit_breaker import CircuitBreaker, CircuitState
from app.utils.metrics import CIRCUIT_REJECTED_TOTAL

logger = logging.getLogger(__name__)

# Lazy-initialized singletons
_providers: dict[str, TTSProvider] = {}
_circuits: dict[str, CircuitBreaker] = {}


def _init() -> None:
    global _providers, _circuits
    if _providers:
        return

    from app.providers.local_provider import LocalCosyVoiceProvider
    from app.providers.siliconflow_provider import SiliconFlowProvider

    _providers = {
        "local:cosyvoice2": LocalCosyVoiceProvider(),
        "cloud:siliconflow": SiliconFlowProvider(),
    }
    _circuits = {
        name: CircuitBreaker(name.replace(":", "_")) for name in _providers
    }


def _get_chain() -> list[str]:
    return settings.tts_provider_chain_list


async def get_active_provider_async() -> TTSProvider:
    """Return the first available provider in the chain.

    - CLOSED：正常放行。
    - HALF_OPEN：只放行抢到试探权（SET NX）的那一个请求，其余视作仍不可用，
      继续尝试链上的下一个 provider。若链上再无可用 provider，抛 RuntimeError。
    - OPEN：直接跳过，尝试下一个 provider。
    """
    _init()

    for provider_name in _get_chain():
        if provider_name not in _circuits:
            logger.warning(f"Unknown provider in chain: {provider_name}")
            continue
        circuit = _circuits[provider_name]
        state = await circuit.get_state()
        if state == CircuitState.CLOSED:
            return _providers[provider_name]
        if state == CircuitState.HALF_OPEN:
            # 半开探测：只放行一个试探请求，其余降级到下一个 provider。
            # 抢到试探权的调用方负责在成败后 record_success/record_failure。
            if await circuit.try_acquire_probe():
                return _providers[provider_name]
            logger.info(
                f"Provider {provider_name} in HALF_OPEN, probe in progress, skipping"
            )
            CIRCUIT_REJECTED_TOTAL.labels(provider_name).inc()
            continue
        # OPEN：直接跳过并计数
        CIRCUIT_REJECTED_TOTAL.labels(provider_name).inc()

    raise RuntimeError("All TTS providers are unavailable")


def get_circuit(name: str) -> CircuitBreaker | None:
    _init()
    return _circuits.get(name)


def get_circuit_for_provider(provider_name: str) -> CircuitBreaker | None:
    _init()
    return _circuits.get(provider_name)


def get_all_capabilities() -> list[dict]:
    _init()
    return [
        {"provider": name, "capabilities": p.capabilities.model_dump()}
        for name, p in _providers.items()
    ]

"""Provider chain: selects the first non-open provider in the configured chain.

TTS_PROVIDER_CHAIN env var defines the preference order, e.g.:
  "local:cosyvoice2,cloud:siliconflow"
"""

import asyncio
import logging

from app.config import settings
from app.providers.base import TTSProvider
from app.providers.circuit_breaker import CircuitBreaker, CircuitState

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
    """Return the first non-open provider in the chain.
    Raises RuntimeError if all providers are unavailable.
    """
    _init()

    for provider_name in _get_chain():
        if provider_name not in _circuits:
            logger.warning(f"Unknown provider in chain: {provider_name}")
            continue
        state = await _circuits[provider_name].get_state()
        if state != CircuitState.OPEN:
            return _providers[provider_name]

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

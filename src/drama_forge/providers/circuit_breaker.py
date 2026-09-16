# SPDX-FileCopyrightText: 2026 zcbacxc
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Circuit breaker for provider adapters (CLOSED / OPEN / HALF_OPEN).

Infrastructure-level protection only: breaker state is never part of
production definition fingerprints (node / generation-spec / policy).
When OPEN, ``generate()`` short-circuits without calling the inner
provider and returns ``ok=False, retryable=False`` so the Scheduler
does not hammer a failing backend with backoff retries.
"""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum

from drama_forge.providers.base import Provider, ProviderRequest, ProviderResponse

DEFAULT_FAILURE_THRESHOLD = 5
DEFAULT_RECOVERY_TIMEOUT = 30.0
DEFAULT_HALF_OPEN_MAX_CALLS = 1


class CircuitState(StrEnum):
    """Circuit breaker lifecycle states."""

    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    """Thread-safe consecutive-failure circuit breaker.

    Decision: only consecutive failures trip the breaker so isolated
    blips do not open the circuit; recovery_timeout gates the HALF_OPEN
    trial window.
    """

    def __init__(
        self,
        failure_threshold: int = DEFAULT_FAILURE_THRESHOLD,
        recovery_timeout: float = DEFAULT_RECOVERY_TIMEOUT,
        half_open_max_calls: int = DEFAULT_HALF_OPEN_MAX_CALLS,
        clock: Callable[[], float] | None = None,
    ) -> None:
        """Initialize breaker state.

        Args:
            failure_threshold: Consecutive failures required to OPEN.
            recovery_timeout: Seconds before OPEN transitions to HALF_OPEN.
            half_open_max_calls: Concurrent trial calls allowed in HALF_OPEN.
            clock: Monotonic clock; defaults to ``time.monotonic``.
        """
        self.failure_threshold = max(1, int(failure_threshold))
        self.recovery_timeout = max(0.0, float(recovery_timeout))
        self.half_open_max_calls = max(1, int(half_open_max_calls))
        self._clock = clock if clock is not None else time.monotonic
        self._lock = threading.RLock()
        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._opened_at: float | None = None
        self._half_open_calls = 0

    @property
    def state(self) -> CircuitState:
        """Current state, applying OPEN → HALF_OPEN timeout transition."""
        with self._lock:
            self._maybe_half_open()
            return self._state

    @property
    def consecutive_failures(self) -> int:
        """Consecutive failure count since last success."""
        with self._lock:
            return self._consecutive_failures

    def allow_request(self) -> bool:
        """Whether a call may proceed to the inner provider.

        Returns:
            True when CLOSED, or HALF_OPEN with remaining trial slots.
        """
        with self._lock:
            self._maybe_half_open()
            if self._state is CircuitState.CLOSED:
                return True
            if self._state is CircuitState.OPEN:
                return False
            if self._half_open_calls < self.half_open_max_calls:
                self._half_open_calls += 1
                return True
            return False

    def record_success(self) -> None:
        """Reset the breaker to CLOSED after a successful call."""
        with self._lock:
            self._consecutive_failures = 0
            self._half_open_calls = 0
            self._opened_at = None
            self._state = CircuitState.CLOSED

    def record_failure(self) -> None:
        """Count a failure and OPEN when the threshold is reached."""
        with self._lock:
            self._consecutive_failures += 1
            if (
                self._state is CircuitState.HALF_OPEN
                or self._consecutive_failures >= self.failure_threshold
            ):
                self._trip_open()

    def _trip_open(self) -> None:
        """Transition to OPEN and start the recovery timer."""
        self._state = CircuitState.OPEN
        self._opened_at = self._clock()
        self._half_open_calls = 0

    def _maybe_half_open(self) -> None:
        """Move OPEN → HALF_OPEN once recovery_timeout has elapsed."""
        if self._state is not CircuitState.OPEN or self._opened_at is None:
            return
        if self._clock() - self._opened_at >= self.recovery_timeout:
            self._state = CircuitState.HALF_OPEN
            self._half_open_calls = 0


@dataclass(slots=True)
class CircuitBreakerConfig:
    """Infrastructure configuration for provider circuit breakers.

    Decision: enabled defaults to False so factory-registered HTTP adapters
    remain unwrapped (isinstance / attribute compatibility). Opt in via
    ``DRAMA_FORGE_CIRCUIT_ENABLED=1`` or explicit wrap in production setups.
    """

    enabled: bool = False
    failure_threshold: int = DEFAULT_FAILURE_THRESHOLD
    recovery_timeout: float = DEFAULT_RECOVERY_TIMEOUT
    half_open_max_calls: int = DEFAULT_HALF_OPEN_MAX_CALLS


class CircuitBreakerProvider(Provider):
    """Provider decorator that short-circuits when the circuit is OPEN.

    Mirrors the inner provider's id, capabilities, and routing scores so
    circuit state never enters production definition fingerprints.
    """

    def __init__(
        self,
        inner: Provider,
        breaker: CircuitBreaker | None = None,
        config: CircuitBreakerConfig | None = None,
    ) -> None:
        """Wrap a provider with a circuit breaker.

        Args:
            inner: Provider to protect.
            breaker: Optional pre-built breaker; otherwise built from config.
            config: Breaker thresholds when ``breaker`` is omitted.
        """
        self.inner = inner
        cfg = config or CircuitBreakerConfig()
        self.breaker = breaker or CircuitBreaker(
            failure_threshold=cfg.failure_threshold,
            recovery_timeout=cfg.recovery_timeout,
            half_open_max_calls=cfg.half_open_max_calls,
        )
        self.id = inner.id
        self.capabilities = set(inner.capabilities)
        self.quality_score = inner.quality_score
        self.reliability = inner.reliability
        self.cost_score = inner.cost_score
        self.latency_score = inner.latency_score
        self.open_reject_count = 0

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        """Execute via the inner provider unless the circuit is OPEN.

        Args:
            request: ProviderRequest

        Returns:
            ProviderResponse; OPEN short-circuit is ``ok=False``,
            ``retryable=False``.
        """
        if not self.breaker.allow_request():
            self.open_reject_count += 1
            return ProviderResponse(
                ok=False,
                error=f"circuit_open: provider {self.id} is temporarily unavailable",
                retryable=False,
                provider_metadata={
                    "provider": self.id,
                    "circuit_state": self.breaker.state.value,
                    "circuit_open": True,
                },
            )
        try:
            response = self.inner.generate(request)
        except Exception as exc:  # noqa: BLE001 — decorator must not raise
            self.breaker.record_failure()
            return ProviderResponse(
                ok=False,
                error=f"provider_exception: {exc}",
                retryable=True,
                provider_metadata={
                    "provider": self.id,
                    "circuit_state": self.breaker.state.value,
                },
            )
        if response.ok:
            self.breaker.record_success()
        else:
            self.breaker.record_failure()
        return response


def circuit_config_from_env(env: Mapping[str, str] | None = None) -> CircuitBreakerConfig:
    """Build CircuitBreakerConfig from ``DRAMA_FORGE_CIRCUIT_*`` variables.

    Args:
        env: Environment mapping; defaults to ``os.environ``.

    Returns:
        CircuitBreakerConfig (enabled unless explicitly disabled).
    """
    source = os.environ if env is None else env

    def _get(key: str, default: str = "") -> str:
        value = source.get(key)
        if value is None:
            return default
        return str(value).strip()

    def _bool(key: str, default: bool) -> bool:
        raw = _get(key)
        if not raw:
            return default
        return raw.lower() in {"1", "true", "yes", "on"}

    def _int(key: str, default: int) -> int:
        raw = _get(key)
        if not raw:
            return default
        try:
            return int(raw)
        except ValueError:
            return default

    def _float(key: str, default: float) -> float:
        raw = _get(key)
        if not raw:
            return default
        try:
            return float(raw)
        except ValueError:
            return default

    return CircuitBreakerConfig(
        enabled=_bool("DRAMA_FORGE_CIRCUIT_ENABLED", False),
        failure_threshold=_int(
            "DRAMA_FORGE_CIRCUIT_FAILURE_THRESHOLD", DEFAULT_FAILURE_THRESHOLD
        ),
        recovery_timeout=_float(
            "DRAMA_FORGE_CIRCUIT_RECOVERY_TIMEOUT", DEFAULT_RECOVERY_TIMEOUT
        ),
        half_open_max_calls=_int(
            "DRAMA_FORGE_CIRCUIT_HALF_OPEN_MAX_CALLS", DEFAULT_HALF_OPEN_MAX_CALLS
        ),
    )


def maybe_wrap_with_circuit(
    provider: Provider,
    config: CircuitBreakerConfig | None = None,
    env: Mapping[str, str] | None = None,
) -> Provider:
    """Wrap ``provider`` when circuit protection is enabled.

    Args:
        provider: Inner provider instance.
        config: Explicit config; otherwise read from env.
        env: Env mapping used when ``config`` is None.

    Returns:
        CircuitBreakerProvider when enabled, else the original provider.
    """
    cfg = config if config is not None else circuit_config_from_env(env)
    if not cfg.enabled:
        return provider
    if isinstance(provider, CircuitBreakerProvider):
        return provider
    return CircuitBreakerProvider(inner=provider, config=cfg)


__all__ = [
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerProvider",
    "CircuitState",
    "circuit_config_from_env",
    "maybe_wrap_with_circuit",
]

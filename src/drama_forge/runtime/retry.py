# SPDX-FileCopyrightText: 2026 zcbacxc
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Exponential backoff with optional jitter for scheduler-level retries.

Runtime infrastructure only — Domain / Quality layers must not sleep or
compute backoff. The Scheduler owns retry timing; tests set ``base_delay=0``
(or inject a no-op sleeper) so unit tests never block.
"""

from __future__ import annotations

import os
import random
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass

DEFAULT_BASE_DELAY = 0.5
DEFAULT_FACTOR = 2.0
DEFAULT_MAX_DELAY = 30.0
DEFAULT_JITTER = 0.1


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Exponential backoff policy for HARD retryable failures.

    Attributes:
        base_delay: Delay after the first failed attempt (seconds).
            Zero disables sleeping entirely (tests / dry-run).
        factor: Multiplier applied per subsequent attempt.
        max_delay: Upper bound on the computed delay (before jitter).
        jitter: Fraction in ``[0, 1]``; delay is scaled by a uniform
            random factor in ``[1 - jitter, 1]`` to avoid thundering herds.
    """

    base_delay: float = DEFAULT_BASE_DELAY
    factor: float = DEFAULT_FACTOR
    max_delay: float = DEFAULT_MAX_DELAY
    jitter: float = DEFAULT_JITTER

    def delay_for_attempt(
        self,
        attempt: int,
        *,
        rng: random.Random | None = None,
    ) -> float:
        """Compute the backoff delay before retrying after a failure.

        Args:
            attempt: 1-based count of the attempt that just failed.
            rng: Optional random source for deterministic tests.

        Returns:
            Delay in seconds; ``0.0`` when base_delay is non-positive.
        """
        if self.base_delay <= 0:
            return 0.0
        exp = max(0, int(attempt) - 1)
        try:
            raw = self.base_delay * (self.factor**exp)
        except OverflowError:
            raw = self.max_delay
        raw = min(self.max_delay, raw)
        if self.jitter <= 0:
            return max(0.0, raw)
        source = rng if rng is not None else random
        scale = 1.0 - self.jitter * source.random()
        return max(0.0, raw * scale)


def sleep_seconds(
    seconds: float,
    sleeper: Callable[[float], None] | None = None,
) -> None:
    """Sleep for ``seconds`` when positive; injectable for tests.

    Args:
        seconds: Requested delay; non-positive values are no-ops.
        sleeper: Optional callable used instead of ``time.sleep``.

    Returns:
        None
    """
    if seconds <= 0:
        return
    sleep_fn = sleeper if sleeper is not None else time.sleep
    sleep_fn(seconds)


def retry_policy_from_env(env: Mapping[str, str] | None = None) -> RetryPolicy:
    """Build a RetryPolicy from ``DRAMA_FORGE_RETRY_*`` variables.

    Args:
        env: Environment mapping; defaults to ``os.environ``.

    Returns:
        Configured RetryPolicy (defaults when variables are absent/invalid).
    """
    source = os.environ if env is None else env

    def _float(key: str, default: float) -> float:
        raw = (source.get(key) or "").strip()
        if not raw:
            return default
        try:
            return float(raw)
        except ValueError:
            return default

    return RetryPolicy(
        base_delay=_float("DRAMA_FORGE_RETRY_BASE_DELAY", DEFAULT_BASE_DELAY),
        factor=_float("DRAMA_FORGE_RETRY_FACTOR", DEFAULT_FACTOR),
        max_delay=_float("DRAMA_FORGE_RETRY_MAX_DELAY", DEFAULT_MAX_DELAY),
        jitter=_float("DRAMA_FORGE_RETRY_JITTER", DEFAULT_JITTER),
    )


__all__ = [
    "DEFAULT_BASE_DELAY",
    "DEFAULT_FACTOR",
    "DEFAULT_JITTER",
    "DEFAULT_MAX_DELAY",
    "RetryPolicy",
    "retry_policy_from_env",
    "sleep_seconds",
]

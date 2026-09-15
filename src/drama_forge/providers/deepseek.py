# SPDX-FileCopyrightText: 2026 zcbacxc
# SPDX-License-Identifier: AGPL-3.0-or-later
"""DeepSeek as an OpenAI-compatible HTTP preset (no vendor-specific adapter).

DeepSeek exposes an OpenAI-compatible chat API. This module only builds a
:class:`~drama_forge.providers.http_adapter.HttpProviderConfig` preset so
the shared :class:`OpenAICompatibleProvider` can talk to it:

- Base URL: ``https://api.deepseek.com``
- Chat path: ``chat/completions`` (live-verified; ``/v1/chat/completions``
  returns HTTP 405 on the current API)
- Auth: ``Authorization: Bearer <api-key>``
- Models (account-dependent): ``deepseek-flash``, ``deepseek-v4-pro``

Environment variables:
- ``DRAMA_FORGE_DEEPSEEK_BASE_URL`` (default ``https://api.deepseek.com``)
- ``DRAMA_FORGE_DEEPSEEK_API_KEY`` / ``DRAMA_FORGE_DEEPSEEK_API_KEY_ENV``
- ``DRAMA_FORGE_DEEPSEEK_MODEL`` (default ``deepseek-flash``)
- ``DRAMA_FORGE_DEEPSEEK_TIMEOUT`` (default ``60``)
- ``DRAMA_FORGE_DEEPSEEK_ID`` (registry id, default ``deepseek``)
- ``DRAMA_FORGE_PROVIDER_DRY_RUN`` (global dry-run)
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field

from drama_forge.providers.http_adapter import HttpProviderConfig

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_CHAT_PATH = "chat/completions"
DEEPSEEK_DEFAULT_MODEL = "deepseek-flash"
DEEPSEEK_API_KEY_ENV = "DRAMA_FORGE_DEEPSEEK_API_KEY"
DEEPSEEK_CAPABILITIES: set[str] = {
    "text_generation",
    "vision_evaluation",
    "continuity_validation",
    "selection",
}


@dataclass(slots=True)
class DeepSeekPreset:
    """OpenAI-compatible preset targeting the DeepSeek API.

    Attributes:
        base_url: DeepSeek API root.
        chat_path: Relative chat completions path (no ``/v1`` prefix).
        api_key_env: Environment variable holding the API key.
        model: Model id (e.g. ``deepseek-flash``).
        timeout_seconds: Per-request timeout.
        provider_id: Registry id.
        capabilities: Capabilities claimed by this preset.
        max_tokens: Max completion tokens (include reasoning tokens).
        temperature: Sampling temperature.
        dry_run: When True, never open a network connection.
        quality_score: Routing quality score.
        reliability: Routing reliability score.
        cost_score: Routing cost score (higher = cheaper).
        latency_score: Routing latency score (higher = faster).
    """

    base_url: str = DEEPSEEK_BASE_URL
    chat_path: str = DEEPSEEK_CHAT_PATH
    api_key_env: str = DEEPSEEK_API_KEY_ENV
    model: str = DEEPSEEK_DEFAULT_MODEL
    timeout_seconds: float = 60.0
    provider_id: str = "deepseek"
    capabilities: set[str] = field(default_factory=lambda: set(DEEPSEEK_CAPABILITIES))
    max_tokens: int = 4096
    temperature: float = 0.7
    dry_run: bool = False
    quality_score: float = 0.88
    reliability: float = 0.92
    cost_score: float = 0.85
    latency_score: float = 0.75

    def to_http_config(self) -> HttpProviderConfig:
        """Convert to the shared OpenAI-compatible HTTP config.

        Returns:
                    HttpProviderConfig
        """
        return HttpProviderConfig(
            base_url=self.base_url,
            api_key_env=self.api_key_env,
            model=self.model,
            timeout_seconds=self.timeout_seconds,
            provider_id=self.provider_id,
            capabilities=set(self.capabilities),
            capability_map={
                "text_generation": "chat",
                "vision_evaluation": "chat",
                "continuity_validation": "chat",
                "selection": "chat",
            },
            chat_path=self.chat_path,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            dry_run=self.dry_run,
            quality_score=self.quality_score,
            reliability=self.reliability,
            cost_score=self.cost_score,
            latency_score=self.latency_score,
        )


def deepseek_config_from_env(env: Mapping[str, str] | None = None) -> DeepSeekPreset:
    """Build a DeepSeek OpenAI-compatible preset from environment variables.

    Args:
        env: Environment mapping; defaults to ``os.environ``.

    Returns:
        A DeepSeekPreset ready for :meth:`to_http_config`.
    """
    resolved: Mapping[str, str] = os.environ if env is None else env

    def _get(key: str, default: str = "") -> str:
        value = resolved.get(key)
        if value is None:
            return default
        return str(value).strip()

    def _bool(key: str) -> bool:
        return _get(key).lower() in {"1", "true", "yes", "on"}

    def _float(key: str, default: float) -> float:
        raw = _get(key)
        if not raw:
            return default
        try:
            return float(raw)
        except ValueError:
            return default

    api_key_env = _get("DRAMA_FORGE_DEEPSEEK_API_KEY_ENV") or DEEPSEEK_API_KEY_ENV
    return DeepSeekPreset(
        base_url=_get("DRAMA_FORGE_DEEPSEEK_BASE_URL", DEEPSEEK_BASE_URL),
        chat_path=_get("DRAMA_FORGE_DEEPSEEK_CHAT_PATH", DEEPSEEK_CHAT_PATH),
        api_key_env=api_key_env,
        model=_get("DRAMA_FORGE_DEEPSEEK_MODEL", DEEPSEEK_DEFAULT_MODEL),
        timeout_seconds=_float("DRAMA_FORGE_DEEPSEEK_TIMEOUT", 60.0),
        provider_id=_get("DRAMA_FORGE_DEEPSEEK_ID", "deepseek"),
        dry_run=_bool("DRAMA_FORGE_PROVIDER_DRY_RUN")
        or _bool("DRAMA_FORGE_DEEPSEEK_DRY_RUN"),
    )

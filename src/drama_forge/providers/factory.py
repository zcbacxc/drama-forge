# SPDX-FileCopyrightText: 2026 zcbacxc
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Build a default ProviderRegistry from environment configuration.

Environment variables (read via ``os.environ`` unless an ``env`` mapping is
passed to :func:`build_default_registry`):

- ``DRAMA_FORGE_PROVIDER``
    Provider family to register. ``mock`` (or unset) registers only local
    mocks. ``openai_compatible`` (aliases: ``openai``, ``http``) also
    registers an HTTP adapter.
- ``DRAMA_FORGE_PROVIDER_BASE_URL``
    HTTP service root for the OpenAI-compatible adapter
    (default ``https://api.openai.com``).
- ``DRAMA_FORGE_PROVIDER_API_KEY``
    API key value. When set, the adapter uses this variable name by default.
- ``DRAMA_FORGE_PROVIDER_API_KEY_ENV``
    Alternate environment variable *name* that holds the API key
    (default ``DRAMA_FORGE_PROVIDER_API_KEY``). Useful when the secret lives
    under a vendor-specific name.
- ``DRAMA_FORGE_PROVIDER_MODEL``
    Model id sent to the HTTP provider (default ``gpt-4o-mini``).
- ``DRAMA_FORGE_PROVIDER_TIMEOUT``
    Per-request timeout in seconds (default ``30``).
- ``DRAMA_FORGE_PROVIDER_DRY_RUN``
    When ``1``/``true``/``yes``, the HTTP adapter never opens a network
    connection and returns deterministic fallback responses.

Mock providers (``mock-primary``, ``mock-economy``, ``mock-evaluator``) are
always registered when ``enable_mock=True`` so local/dev runs work with zero
configuration and without network access.
"""

from __future__ import annotations

import os
from collections.abc import Mapping

from drama_forge.providers.adapters import MockEvaluatorProvider, MockProvider
from drama_forge.providers.http_adapter import HttpProviderConfig, OpenAICompatibleProvider
from drama_forge.providers.registry import ProviderRegistry

_TRUTHY = {"1", "true", "yes", "on"}
_HTTP_KINDS = {"openai_compatible", "openai", "http", "openai-compatible"}
_MOCK_KINDS = {"", "mock", "local", "none"}


def _env_get(env: Mapping[str, str], key: str, default: str = "") -> str:
    value = env.get(key)
    if value is None:
        return default
    return str(value).strip()


def _env_bool(env: Mapping[str, str], key: str) -> bool:
    return _env_get(env, key).lower() in _TRUTHY


def _env_float(env: Mapping[str, str], key: str, default: float) -> float:
    raw = _env_get(env, key)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def register_mock_providers(registry: ProviderRegistry) -> None:
    """Register the standard local mock provider set.

    Mirrors the Engine defaults so factory-built registries behave the same
    as the facade's built-in mocks (primary / economy / evaluator).
    """
    registry.register(MockProvider("mock-primary", quality_score=0.9))
    registry.register(
        MockProvider(
            "mock-economy",
            quality_score=0.6,
            cost_score=0.95,
            latency_score=0.95,
        )
    )
    registry.register(MockEvaluatorProvider())


def http_config_from_env(env: Mapping[str, str]) -> HttpProviderConfig:
    """Build HttpProviderConfig from environment variables."""
    api_key_env = _env_get(env, "DRAMA_FORGE_PROVIDER_API_KEY_ENV")
    if not api_key_env:
        api_key_env = "DRAMA_FORGE_PROVIDER_API_KEY"
    return HttpProviderConfig(
        base_url=_env_get(
            env, "DRAMA_FORGE_PROVIDER_BASE_URL", "https://api.openai.com"
        ),
        api_key_env=api_key_env,
        model=_env_get(env, "DRAMA_FORGE_PROVIDER_MODEL", "gpt-4o-mini"),
        timeout_seconds=_env_float(env, "DRAMA_FORGE_PROVIDER_TIMEOUT", 30.0),
        provider_id=_env_get(env, "DRAMA_FORGE_PROVIDER_ID", "openai-compatible"),
        dry_run=_env_bool(env, "DRAMA_FORGE_PROVIDER_DRY_RUN"),
    )


def build_default_registry(
    env: dict[str, str] | None = None,
    enable_mock: bool = True,
    http_config: HttpProviderConfig | None = None,
) -> ProviderRegistry:
    """Build a ProviderRegistry from environment configuration.

    Args:
        env: Environment mapping; defaults to ``os.environ``.
        enable_mock: When True, always register local mock providers.
        http_config: Optional explicit HTTP config; overrides env-derived
            HTTP settings when the env requests an HTTP provider.

    Returns:
        A registry with mocks (optional) and, when configured, an HTTP provider.
    """
    resolved_env: Mapping[str, str] = os.environ if env is None else env
    registry = ProviderRegistry()
    if enable_mock:
        register_mock_providers(registry)

    kind = _env_get(resolved_env, "DRAMA_FORGE_PROVIDER").lower()
    if kind in _MOCK_KINDS:
        return registry
    if kind in _HTTP_KINDS:
        config = http_config or http_config_from_env(resolved_env)
        registry.register(OpenAICompatibleProvider(config=config, env=dict(resolved_env)))
        return registry
    # Unknown kind: keep mocks (if any) rather than failing hard.
    return registry

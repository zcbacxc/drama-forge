# SPDX-FileCopyrightText: 2026 zcbacxc
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Provider registry."""

from __future__ import annotations

from drama_forge.providers.base import Provider


class ProviderRegistry:
    """Registry of available providers."""

    def __init__(self) -> None:
        self._providers: dict[str, Provider] = {}

    def register(self, provider: Provider) -> Provider:
        """Register a provider instance."""
        self._providers[provider.id] = provider
        return provider

    def get(self, provider_id: str) -> Provider | None:
        """Get provider by id."""
        return self._providers.get(provider_id)

    def candidates_for(self, capability: str) -> list[Provider]:
        """List providers supporting a capability."""
        return [p for p in self._providers.values() if p.supports(capability)]

    def all(self) -> list[Provider]:
        """List all providers."""
        return list(self._providers.values())

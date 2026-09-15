# SPDX-FileCopyrightText: 2026 zcbacxc
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Provider registry."""

from __future__ import annotations

from drama_forge.providers.base import Provider


class ProviderRegistry:
    """Registry of available providers."""

    def __init__(self) -> None:
        """__init__.

        Args:
                    None.
        """
        self._providers: dict[str, Provider] = {}

    def register(self, provider: Provider) -> Provider:
        """Register a provider instance.

        Args:
                    provider: Provider

        Returns:
                    Provider
        """
        self._providers[provider.id] = provider
        return provider

    def get(self, provider_id: str) -> Provider | None:
        """Get provider by id.

        Args:
                    provider_id: str

        Returns:
                    Provider | None
        """
        return self._providers.get(provider_id)

    def candidates_for(self, capability: str) -> list[Provider]:
        """List providers supporting a capability.

        Args:
                    capability: str

        Returns:
                    list[Provider]
        """
        return [p for p in self._providers.values() if p.supports(capability)]

    def all(self) -> list[Provider]:
        """List all providers.

        Returns:
                    list[Provider]
        """
        return list(self._providers.values())

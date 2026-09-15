# SPDX-FileCopyrightText: 2026 zcbacxc
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Strategy-based provider router with decision records."""

from __future__ import annotations

from typing import Any

from drama_forge.domain.production import DecisionRecord
from drama_forge.providers.base import Provider
from drama_forge.providers.registry import ProviderRegistry


class ProviderRouter:
    """Select providers using per-node strategy policy.

    Strategies:
    - quality_first: prioritize quality_score
    - cost_first: prioritize cost_score (higher = cheaper/better)
    - continuity: prioritize quality + reliability
    - reliability_first: prioritize reliability (with light quality/latency)
    - balanced: weighted mix including latency_score (default)

    Per-capability overrides:
        policy may include ``by_capability`` mapping capability name to a
        sub-policy (``provider_id`` / ``strategy``). The sub-policy is merged
        over the base policy for that capability only, so production can pin
        DeepSeek to text/eval and SiliconFlow to image without changing the
        production graph.
    """

    def __init__(self, registry: ProviderRegistry) -> None:
        """__init__.

        Args:
                    registry: ProviderRegistry
        """
        self.registry = registry

    @staticmethod
    def resolve_policy(capability: str, policy: dict[str, Any] | None) -> dict[str, Any]:
        """Merge base policy with any per-capability override.

        Args:
            capability: Capability being routed.
            policy: Base routing policy, may contain ``by_capability``.

        Returns:
            Effective policy for this capability (``by_capability`` removed).
        """
        base = dict(policy or {})
        by_capability = base.get("by_capability")
        if isinstance(by_capability, dict):
            override = by_capability.get(capability)
            if isinstance(override, dict):
                base = {**base, **override}
        base.pop("by_capability", None)
        return base

    def select(
        self,
        capability: str,
        policy: dict[str, Any] | None = None,
        subject: str = "",
        execution_id: str | None = None,
    ) -> tuple[Provider, DecisionRecord]:
        """Select a provider and record the decision.

        Args:
            capability: Required capability name.
            policy: Routing policy with optional strategy, forced provider_id,
                and per-capability ``by_capability`` overrides.
            subject: Decision subject label.
            execution_id: Current execution id for the decision record.

        Returns:
            Tuple of (selected provider, decision record).

        Raises:
            RuntimeError: If no provider supports the capability.
        """
        policy = self.resolve_policy(capability, policy)
        strategy = str(policy.get("strategy", "balanced"))
        candidates = self.registry.candidates_for(capability)
        if not candidates:
            raise RuntimeError(f"no provider supports capability: {capability}")

        forced = policy.get("provider_id")
        if forced:
            provider = self.registry.get(str(forced))
            if provider and provider.supports(capability):
                decision = DecisionRecord.create(
                    decision_type="provider_routing",
                    subject=subject or capability,
                    candidates=[p.id for p in candidates],
                    policy=policy,
                    selected=provider.id,
                    reason="forced by provider policy",
                    execution_id=execution_id,
                )
                return provider, decision

        scored = [(self._score(p, strategy), p) for p in candidates]
        scored.sort(key=lambda item: item[0], reverse=True)
        selected = scored[0][1]
        decision = DecisionRecord.create(
            decision_type="provider_routing",
            subject=subject or capability,
            candidates=[p.id for p in candidates],
            policy=policy,
            selected=selected.id,
            reason=f"strategy={strategy}; score={scored[0][0]:.3f}",
            evidence={
                "scores": {p.id: self._score(p, strategy) for _, p in scored},
            },
            execution_id=execution_id,
        )
        return selected, decision

    @staticmethod
    def _score(provider: Provider, strategy: str) -> float:
        """Compute routing score for a strategy."""
        if strategy == "quality_first":
            return provider.quality_score
        if strategy == "cost_first":
            return provider.cost_score
        if strategy == "continuity":
            return 0.7 * provider.quality_score + 0.3 * provider.reliability
        if strategy == "reliability_first":
            return (
                0.25 * provider.quality_score
                + 0.6 * provider.reliability
                + 0.15 * provider.latency_score
            )
        # balanced (latency-aware)
        return (
            0.4 * provider.quality_score
            + 0.2 * provider.reliability
            + 0.2 * provider.cost_score
            + 0.2 * provider.latency_score
        )

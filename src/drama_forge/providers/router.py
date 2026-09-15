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
    - balanced: weighted mix (default)
    """

    def __init__(self, registry: ProviderRegistry) -> None:
        self.registry = registry

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
            policy: Routing policy with optional strategy and forced provider_id.
            subject: Decision subject label.
            execution_id: Current execution id for the decision record.

        Returns:
            Tuple of (selected provider, decision record).

        Raises:
            RuntimeError: If no provider supports the capability.
        """
        policy = policy or {}
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
        # balanced
        return (
            0.4 * provider.quality_score
            + 0.2 * provider.reliability
            + 0.2 * provider.cost_score
            + 0.2 * provider.latency_score
        )

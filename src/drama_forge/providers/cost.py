# SPDX-FileCopyrightText: 2026 zcbacxc
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Per-execution provider cost and usage accumulation."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any

from drama_forge.providers.base import ProviderResponse


@dataclass(slots=True)
class ExecutionCostSummary:
    """Aggregated cost/usage for one execution."""

    execution_id: str
    total_cost: float = 0.0
    call_count: int = 0
    failed_calls: int = 0
    usage: dict[str, float] = field(default_factory=dict)
    by_provider: dict[str, float] = field(default_factory=dict)
    by_capability: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a plain-dict view of the summary.

        Returns:
                    dict[str, Any]
        """
        return {
            "execution_id": self.execution_id,
            "total_cost": self.total_cost,
            "call_count": self.call_count,
            "failed_calls": self.failed_calls,
            "usage": dict(self.usage),
            "by_provider": dict(self.by_provider),
            "by_capability": dict(self.by_capability),
        }


class CostTracker:
    """Accumulate provider cost and usage keyed by execution_id.

    Pure in-memory bookkeeping; not a persistence store. Callers record each
    ProviderResponse after a task completes and read summaries at the end of
    an execution (or for budget checks mid-run).
    """

    def __init__(self) -> None:
        """__init__.

        Args:
                    None.
        """
        # Guard _summaries for concurrent workers (Scheduler max_workers>1).
        self._lock = threading.RLock()
        self._summaries: dict[str, ExecutionCostSummary] = {}

    def record(
        self,
        execution_id: str,
        response: ProviderResponse | None = None,
        *,
        provider_id: str = "",
        capability: str = "",
        cost: float | None = None,
        usage: dict[str, Any] | None = None,
    ) -> ExecutionCostSummary:
        """Record one generation outcome against an execution.

        Args:
            execution_id: Execution (or run) identifier.
            response: Optional normalized provider response to fold in.
            provider_id: Provider id; taken from response metadata when empty.
            capability: Capability name for per-capability rollup.
            cost: Explicit cost override; defaults to ``response.cost``.
            usage: Explicit usage override; defaults to ``response.usage``.

        Returns:
            Updated summary for the execution.
        """
        with self._lock:
            summary = self._summaries.setdefault(
                execution_id, ExecutionCostSummary(execution_id=execution_id)
            )
            resolved_provider = provider_id
            resolved_cost = 0.0
            resolved_usage: dict[str, Any] = dict(usage or {})
            ok = True
            if response is not None:
                ok = response.ok
                if not resolved_provider:
                    resolved_provider = str(
                        response.provider_metadata.get("provider") or ""
                    )
                if cost is None:
                    resolved_cost = float(response.cost or 0.0)
                if not resolved_usage:
                    resolved_usage = dict(response.usage or {})
            if cost is not None:
                resolved_cost = float(cost)

            summary.call_count += 1
            if not ok:
                summary.failed_calls += 1
            summary.total_cost += resolved_cost
            if resolved_provider:
                summary.by_provider[resolved_provider] = (
                    summary.by_provider.get(resolved_provider, 0.0) + resolved_cost
                )
            if capability:
                summary.by_capability[capability] = (
                    summary.by_capability.get(capability, 0.0) + resolved_cost
                )
            for key, value in resolved_usage.items():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    summary.usage[key] = summary.usage.get(key, 0.0) + float(value)
                else:
                    # keep non-numeric usage as last-seen marker under a string bucket
                    summary.usage[key] = value  # type: ignore[assignment]
            return summary

    def summary(self, execution_id: str) -> ExecutionCostSummary:
        """Return the summary for an execution (empty if unknown).

        Args:
                    execution_id: str

        Returns:
                    ExecutionCostSummary
        """
        with self._lock:
            return self._summaries.get(
                execution_id, ExecutionCostSummary(execution_id=execution_id)
            )

    def total_cost(self, execution_id: str) -> float:
        """Return total cost for an execution.

        Args:
                    execution_id: str

        Returns:
                    float
        """
        return self.summary(execution_id).total_cost

    def executions(self) -> list[str]:
        """List execution ids that have recorded costs.

        Returns:
                    list[str]
        """
        with self._lock:
            return list(self._summaries.keys())

    def reset(self, execution_id: str | None = None) -> None:
        """Clear one execution, or all when execution_id is None.

        Args:
                    execution_id: default None

        Returns:
                    None
        """
        with self._lock:
            if execution_id is None:
                self._summaries.clear()
                return
            self._summaries.pop(execution_id, None)

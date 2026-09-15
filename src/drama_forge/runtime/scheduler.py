"""Production graph scheduler and worker loop."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from drama_forge.domain.common import ExecutionStatus, NodeStatus, new_id
from drama_forge.domain.production import GraphNode, ProductionGraph
from drama_forge.runtime.checkpoint import Checkpoint, CheckpointStore
from drama_forge.runtime.events import EventBus


class NodeExecutor(Protocol):
    """Protocol for executing a single production node."""

    def execute(self, node: GraphNode, context: ExecutionContext) -> TaskResult:
        """Execute one node and return its result."""
        ...


@dataclass(slots=True)
class ExecutionContext:
    """Shared state passed to workers during an execution."""

    execution_id: str
    graph: ProductionGraph
    assets: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, Any] = field(default_factory=dict)
    candidates: dict[str, Any] = field(default_factory=dict)
    decision_records: list[Any] = field(default_factory=list)
    quality_results: list[Any] = field(default_factory=list)
    events: EventBus = field(default_factory=EventBus)
    config: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TaskResult:
    """Result submitted by a worker for one node."""

    node_id: str
    success: bool
    artifact_ids: list[str] = field(default_factory=list)
    candidate_ids: list[str] = field(default_factory=list)
    output_fingerprints: dict[str, str] = field(default_factory=dict)
    error: str | None = None
    outputs: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ExecutionPlan:
    """Snapshot binding graph version + config for one run."""

    id: str
    graph_id: str
    graph_fingerprint: str
    input_fingerprint: str
    config: dict[str, Any] = field(default_factory=dict)
    provider_policy: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        graph: ProductionGraph,
        input_fingerprint: str,
        config: dict[str, Any] | None = None,
        provider_policy: dict[str, Any] | None = None,
    ) -> ExecutionPlan:
        """Create an execution plan for a graph."""
        return cls(
            id=new_id("exec"),
            graph_id=graph.id,
            graph_fingerprint=graph.fingerprint(),
            input_fingerprint=input_fingerprint,
            config=config or {},
            provider_policy=provider_policy or {},
        )


class Scheduler:
    """Run production graph nodes whose dependencies are satisfied."""

    def __init__(
        self,
        executor: NodeExecutor,
        checkpoint_store: CheckpointStore | None = None,
        max_attempts: int = 3,
        fingerprint_cache: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self.executor = executor
        self.checkpoint_store = checkpoint_store or CheckpointStore()
        self.max_attempts = max_attempts
        self.fingerprint_cache: dict[str, dict[str, Any]] = (
            fingerprint_cache if fingerprint_cache is not None else {}
        )

    def run(
        self,
        graph: ProductionGraph,
        context: ExecutionContext,
        resume_from: Checkpoint | None = None,
    ) -> ExecutionStatus:
        """Execute the graph until terminal state.

        Args:
            graph: Production graph to run.
            context: Shared execution context.
            resume_from: Optional checkpoint to resume from.

        Returns:
            Final execution status.
        """
        if resume_from is not None:
            self._apply_checkpoint(graph, resume_from, context)
            context.events.emit("execution.resumed", context.execution_id)

        graph.recompute_all_fingerprints()
        self.checkpoint_store.save(
            Checkpoint(
                graph_id=graph.id,
                execution_id=context.execution_id,
                graph_fingerprint=graph.fingerprint(),
                input_fingerprint=str(context.config.get("input_fingerprint", "")),
                node_status={nid: n.status.value for nid, n in graph.nodes.items()},
            )
        )
        context.events.emit("execution.started", context.execution_id)

        progress = True
        while progress:
            progress = False
            ready = graph.ready_nodes()
            for node in ready:
                progress = True
                self._run_node(node, graph, context)

        statuses = {nid: n.status for nid, n in graph.nodes.items()}
        self.checkpoint_store.update_status_from_graph(context.execution_id, statuses)

        failed = [s for s in statuses.values() if s == NodeStatus.FAILED]
        invalidated = [s for s in statuses.values() if s == NodeStatus.INVALIDATED]
        succeeded = [s for s in statuses.values() if s == NodeStatus.SUCCEEDED]

        if failed and not succeeded:
            status = ExecutionStatus.FAILED
        elif failed or invalidated:
            status = ExecutionStatus.PARTIAL
        elif succeeded and len(succeeded) == len(statuses):
            status = ExecutionStatus.SUCCEEDED
        elif succeeded:
            status = ExecutionStatus.PARTIAL
        else:
            status = ExecutionStatus.FAILED

        cp = self.checkpoint_store.load(context.execution_id)
        if cp:
            cp.execution_status = status.value
            cp.failure_state = {
                nid: n.error for nid, n in graph.nodes.items() if n.error
            }
            self.checkpoint_store.save(cp)
        context.events.emit("execution.finished", context.execution_id, status=status.value)
        return status

    def _run_node(
        self,
        node: GraphNode,
        graph: ProductionGraph,
        context: ExecutionContext,
    ) -> None:
        """Execute one node with retry semantics."""
        node.status = NodeStatus.RUNNING
        node.attempt += 1
        context.events.emit("node.started", node.id, attempt=node.attempt)

        # Fingerprint reuse via shared cache (survives across graph rebuilds)
        cache_key = node.fingerprint
        enable_reuse = context.config.get("enable_fingerprint_reuse", True)
        if cache_key and enable_reuse:
            cached = self.fingerprint_cache.get(cache_key)
            if cached:
                node.status = NodeStatus.SUCCEEDED
                node.artifact_ids = list(cached.get("artifact_ids", []))
                node.candidate_ids = list(cached.get("candidate_ids", []))
                node.output_fingerprints = dict(cached.get("output_fingerprints", {}))
                # rehydrate outputs into current context if missing
                for aid in node.artifact_ids:
                    if aid not in context.artifacts:
                        # leave lookup to artifact store consumers
                        pass
                context.events.emit("node.reused", node.id, fingerprint=cache_key)
                self._persist(graph, context)
                return

        try:
            result = self.executor.execute(node, context)
        except Exception as exc:  # noqa: BLE001 — worker boundary
            result = TaskResult(node_id=node.id, success=False, error=str(exc))

        if result.success:
            node.status = NodeStatus.SUCCEEDED
            node.artifact_ids = result.artifact_ids
            node.candidate_ids = result.candidate_ids
            node.output_fingerprints = result.output_fingerprints
            node.error = None
            if cache_key:
                self.fingerprint_cache[cache_key] = {
                    "artifact_ids": list(result.artifact_ids),
                    "candidate_ids": list(result.candidate_ids),
                    "output_fingerprints": dict(result.output_fingerprints),
                }
            context.events.emit("node.succeeded", node.id)
        else:
            node.error = result.error or "unknown error"
            if node.attempt < self.max_attempts:
                node.status = NodeStatus.RETRYING
                context.events.emit("node.retry", node.id, error=node.error)
                # retry immediately (sync loop)
                return self._run_node(node, graph, context)
            node.status = NodeStatus.FAILED
            context.events.emit("node.failed", node.id, error=node.error)

        self._persist(graph, context)

    def _persist(self, graph: ProductionGraph, context: ExecutionContext) -> None:
        """Save checkpoint after a node transition."""
        statuses = {nid: n.status for nid, n in graph.nodes.items()}
        cp = self.checkpoint_store.load(context.execution_id)
        if cp is None:
            cp = Checkpoint(
                graph_id=graph.id,
                execution_id=context.execution_id,
                graph_fingerprint=graph.fingerprint(),
                input_fingerprint=str(context.config.get("input_fingerprint", "")),
            )
        cp.node_status = {k: v.value for k, v in statuses.items()}
        cp.completed_nodes = [
            nid for nid, st in statuses.items() if st == NodeStatus.SUCCEEDED
        ]
        cp.node_outputs = {
            nid: {
                "artifact_ids": n.artifact_ids,
                "candidate_ids": n.candidate_ids,
                "output_fingerprints": n.output_fingerprints,
            }
            for nid, n in graph.nodes.items()
            if n.status == NodeStatus.SUCCEEDED
        }
        cp.artifact_refs = {
            nid: n.artifact_ids for nid, n in graph.nodes.items() if n.artifact_ids
        }
        cp.candidate_refs = {
            nid: n.candidate_ids for nid, n in graph.nodes.items() if n.candidate_ids
        }
        self.checkpoint_store.save(cp)

    def _apply_checkpoint(
        self,
        graph: ProductionGraph,
        checkpoint: Checkpoint,
        context: ExecutionContext,
    ) -> None:
        """Restore graph node states from checkpoint."""
        for nid, status_name in checkpoint.node_status.items():
            if nid in graph.nodes:
                graph.nodes[nid].status = NodeStatus(status_name)
        for nid, outputs in checkpoint.node_outputs.items():
            if nid in graph.nodes:
                graph.nodes[nid].artifact_ids = outputs.get("artifact_ids", [])
                graph.nodes[nid].candidate_ids = outputs.get("candidate_ids", [])
                graph.nodes[nid].output_fingerprints = outputs.get(
                    "output_fingerprints", {}
                )

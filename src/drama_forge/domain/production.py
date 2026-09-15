# SPDX-FileCopyrightText: 2026 zcbacxc
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Production model: manifest, spec, graph nodes/edges, fingerprints."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from drama_forge.domain.common import (
    MetadataBag,
    NodeStatus,
    new_id,
    stable_hash,
)


@dataclass(slots=True)
class CanonicalGenerationSpec:
    """What to produce at a node 鈥?provider-agnostic generation contract."""

    node_id: str
    capability: str
    inputs: dict[str, Any] = field(default_factory=dict)
    character_asset_ids: list[str] = field(default_factory=list)
    location_asset_id: str | None = None
    style_constraints: dict[str, Any] = field(default_factory=dict)
    continuity_constraints: dict[str, Any] = field(default_factory=dict)
    camera_spec: dict[str, Any] = field(default_factory=dict)
    motion_spec: dict[str, Any] = field(default_factory=dict)
    audio_requirements: dict[str, Any] = field(default_factory=dict)
    output_requirements: dict[str, Any] = field(default_factory=dict)
    selection_policy: dict[str, Any] = field(default_factory=dict)
    candidate_count: int = 1
    metadata: MetadataBag = field(default_factory=MetadataBag)

    def fingerprint(self) -> str:
        """Fingerprint of generation conditions for reuse/dedup.

        Excludes node_id so replanning the same production conditions
        yields the same fingerprint.
        """
        return stable_hash(
            {
                "capability": self.capability,
                "inputs": self.inputs,
                "character_asset_ids": sorted(self.character_asset_ids),
                "location_asset_id": self.location_asset_id,
                "style_constraints": self.style_constraints,
                "continuity_constraints": self.continuity_constraints,
                "output_requirements": self.output_requirements,
                "selection_policy": self.selection_policy,
                "candidate_count": self.candidate_count,
            }
        )


@dataclass(slots=True)
class GraphNode:
    """One production action in the production graph."""

    id: str
    name: str
    action: str
    status: NodeStatus = NodeStatus.PENDING
    generation_spec: CanonicalGenerationSpec | None = None
    input_asset_ids: list[str] = field(default_factory=list)
    output_asset_id: str | None = None
    policy: dict[str, Any] = field(default_factory=dict)
    fingerprint: str = ""
    output_fingerprints: dict[str, str] = field(default_factory=dict)
    artifact_ids: list[str] = field(default_factory=list)
    candidate_ids: list[str] = field(default_factory=list)
    error: str | None = None
    attempt: int = 0
    metadata: MetadataBag = field(default_factory=MetadataBag)

    @classmethod
    def create(
        cls,
        name: str,
        action: str,
        **kwargs: object,
    ) -> GraphNode:
        """Create a production graph node with a content-stable id."""
        node_id = f"node_{stable_hash({'n': name, 'a': action})[:12]}"
        return cls(id=node_id, name=name, action=action, **kwargs)  # type: ignore[arg-type]

    def compute_fingerprint(self, provider_policy: dict[str, Any] | None = None) -> str:
        """Recompute and store node fingerprint from definition + inputs + policy."""
        spec_fp = self.generation_spec.fingerprint() if self.generation_spec else ""
        self.fingerprint = stable_hash(
            {
                "name": self.name,
                "action": self.action,
                "spec": spec_fp,
                "inputs": sorted(self.input_asset_ids),
                "policy": provider_policy or self.policy,
            }
        )
        return self.fingerprint


@dataclass(slots=True)
class GraphEdge:
    """Dependency edge: source must succeed before target runs."""

    id: str
    source_id: str
    target_id: str
    kind: str = "depends_on"

    @classmethod
    def create(cls, source_id: str, target_id: str, kind: str = "depends_on") -> GraphEdge:
        """Create a dependency edge."""
        return cls(id=new_id("edge"), source_id=source_id, target_id=target_id, kind=kind)


@dataclass(slots=True)
class ProductionGraph:
    """Core production model: nodes + edges + policies."""

    id: str
    name: str
    version: int = 1
    nodes: dict[str, GraphNode] = field(default_factory=dict)
    edges: list[GraphEdge] = field(default_factory=list)
    policy: dict[str, Any] = field(default_factory=dict)
    metadata: MetadataBag = field(default_factory=MetadataBag)

    @classmethod
    def create(cls, name: str, **kwargs: object) -> ProductionGraph:
        """Create an empty production graph."""
        return cls(id=new_id("graph"), name=name, **kwargs)  # type: ignore[arg-type]

    def add_node(self, node: GraphNode) -> GraphNode:
        """Register a node."""
        self.nodes[node.id] = node
        return node

    def add_edge(self, edge: GraphEdge) -> GraphEdge:
        """Register a dependency edge."""
        self.edges.append(edge)
        return edge

    def dependents(self, node_id: str) -> list[str]:
        """Return node ids that directly depend on the given node."""
        return [e.target_id for e in self.edges if e.source_id == node_id]

    def dependencies(self, node_id: str) -> list[str]:
        """Return node ids that the given node directly depends on."""
        return [e.source_id for e in self.edges if e.target_id == node_id]

    def ready_nodes(self) -> list[GraphNode]:
        """Nodes whose dependencies have all succeeded and are still pending."""
        ready: list[GraphNode] = []
        for node in self.nodes.values():
            if node.status not in (NodeStatus.PENDING, NodeStatus.READY, NodeStatus.RETRYING):
                continue
            deps = self.dependencies(node.id)
            if all(self.nodes[d].status == NodeStatus.SUCCEEDED for d in deps if d in self.nodes):
                node.status = NodeStatus.READY
                ready.append(node)
        return ready

    def recompute_all_fingerprints(self) -> None:
        """Recompute fingerprints for every node."""
        for node in self.nodes.values():
            node.compute_fingerprint(self.policy)

    def fingerprint(self) -> str:
        """Structural fingerprint of the whole graph."""
        return stable_hash(
            {
                "name": self.name,
                "version": self.version,
                "nodes": sorted(
                    (n.id, n.name, n.action, n.fingerprint) for n in self.nodes.values()
                ),
                "edges": sorted((e.source_id, e.target_id, e.kind) for e in self.edges),
            }
        )

    def topological_order(self) -> list[GraphNode]:
        """Return nodes in dependency order (stable by insertion if cycle-free)."""
        indegree = {nid: 0 for nid in self.nodes}
        for edge in self.edges:
            if edge.target_id in indegree:
                indegree[edge.target_id] += 1
        queue = [nid for nid, deg in indegree.items() if deg == 0]
        # preserve insertion order
        order_ids = list(self.nodes.keys())
        queue = [nid for nid in order_ids if indegree[nid] == 0]
        result: list[GraphNode] = []
        seen = set()
        while queue:
            current = queue.pop(0)
            if current in seen:
                continue
            seen.add(current)
            result.append(self.nodes[current])
            for dep in self.dependents(current):
                indegree[dep] -= 1
                if indegree[dep] == 0:
                    queue.append(dep)
        return result

    def invalidate_from(self, node_ids: set[str]) -> set[str]:
        """Propagate INVALIDATED status to all transitive dependents.

        Args:
            node_ids: Seed nodes already known dirty/invalid.

        Returns:
            Full set of invalidated node ids including seeds.
        """
        invalidated = set(node_ids)
        stack = list(node_ids)
        while stack:
            current = stack.pop()
            for dependent in self.dependents(current):
                if dependent not in invalidated:
                    invalidated.add(dependent)
                    stack.append(dependent)
        for nid in invalidated:
            if nid in self.nodes:
                self.nodes[nid].status = NodeStatus.INVALIDATED
        return invalidated

    def reset_invalidated_to_pending(self) -> list[str]:
        """Reset INVALIDATED nodes to PENDING so they can be re-executed."""
        reset: list[str] = []
        for node in self.nodes.values():
            if node.status == NodeStatus.INVALIDATED:
                node.status = NodeStatus.PENDING
                node.error = None
                node.attempt = 0
                node.artifact_ids = []
                node.candidate_ids = []
                reset.append(node.id)
        return reset


@dataclass(slots=True)
class ProductionSpec:
    """Bridge from story needs to production graph requirements."""

    id: str
    story_id: str
    story_version: int
    scene_requirements: dict[str, dict[str, Any]] = field(default_factory=dict)
    shot_requirements: dict[str, dict[str, Any]] = field(default_factory=dict)
    style_constraints: dict[str, Any] = field(default_factory=dict)
    continuity_requirements: dict[str, Any] = field(default_factory=dict)
    required_character_asset_ids: list[str] = field(default_factory=list)
    required_scene_asset_ids: list[str] = field(default_factory=list)
    metadata: MetadataBag = field(default_factory=MetadataBag)

    @classmethod
    def create(cls, story_id: str, story_version: int = 1) -> ProductionSpec:
        """Create an empty production spec."""
        return cls(id=new_id("spec"), story_id=story_id, story_version=story_version)

    def fingerprint(self) -> str:
        """Fingerprint of production requirements."""
        return stable_hash(
            {
                "story_id": self.story_id,
                "story_version": self.story_version,
                "scene_requirements": self.scene_requirements,
                "shot_requirements": self.shot_requirements,
                "style_constraints": self.style_constraints,
            }
        )


@dataclass(slots=True)
class ProductionManifest:
    """Declarative contract for one production run."""

    id: str
    story_version: int
    story_id: str
    production_spec_id: str
    graph_id: str
    capability_policy: dict[str, Any] = field(default_factory=dict)
    provider_policy: dict[str, Any] = field(default_factory=dict)
    selection_policy: dict[str, Any] = field(default_factory=dict)
    quality_policy: dict[str, Any] = field(default_factory=dict)
    output_policy: dict[str, Any] = field(default_factory=dict)
    asset_versions: dict[str, int] = field(default_factory=dict)
    schema_version: str = "1.0"
    metadata: MetadataBag = field(default_factory=MetadataBag)

    @classmethod
    def create(
        cls,
        story_id: str,
        story_version: int,
        production_spec_id: str,
        graph_id: str,
        **kwargs: object,
    ) -> ProductionManifest:
        """Create a production manifest."""
        return cls(
            id=new_id("man"),
            story_id=story_id,
            story_version=story_version,
            production_spec_id=production_spec_id,
            graph_id=graph_id,
            **kwargs,  # type: ignore[arg-type]
        )

    def validate(self) -> list[str]:
        """Schema-level validation errors (empty if valid)."""
        errors: list[str] = []
        if not self.story_id:
            errors.append("story_id is required")
        if not self.production_spec_id:
            errors.append("production_spec_id is required")
        if not self.graph_id:
            errors.append("graph_id is required")
        if self.story_version < 1:
            errors.append("story_version must be >= 1")
        return errors

    def fingerprint(self) -> str:
        """Fingerprint of the production contract."""
        return stable_hash(
            {
                "story_id": self.story_id,
                "story_version": self.story_version,
                "production_spec_id": self.production_spec_id,
                "graph_id": self.graph_id,
                "capability_policy": self.capability_policy,
                "provider_policy": self.provider_policy,
                "selection_policy": self.selection_policy,
                "quality_policy": self.quality_policy,
            }
        )


@dataclass(slots=True)
class DecisionRecord:
    """Why a routing/selection/gate decision was made."""

    id: str
    decision_type: str
    subject: str
    candidates: list[str] = field(default_factory=list)
    policy: dict[str, Any] = field(default_factory=dict)
    selected: str | None = None
    reason: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)
    execution_id: str | None = None
    created_at: str = ""

    @classmethod
    def create(
        cls,
        decision_type: str,
        subject: str,
        **kwargs: object,
    ) -> DecisionRecord:
        """Create a decision record."""
        from drama_forge.domain.asset import utc_now_iso

        return cls(
            id=new_id("dec"),
            decision_type=decision_type,
            subject=subject,
            created_at=utc_now_iso(),
            **kwargs,  # type: ignore[arg-type]
        )

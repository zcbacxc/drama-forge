"""Repair planner: preflight and post-generation local repairs."""

from __future__ import annotations

from drama_forge.domain.common import IssueType, RepairKind
from drama_forge.domain.production import ProductionGraph
from drama_forge.domain.quality import Issue, RepairPlan


class RepairPlanner:
    """Compute minimal repair scope from structured issues."""

    def plan(
        self,
        issues: list[Issue],
        graph: ProductionGraph,
        kind: RepairKind | None = None,
    ) -> RepairPlan:
        """Build a repair plan that invalidates only affected nodes.

        Preflight issues (missing input/spec) target the node itself.
        Post-generation continuity/quality issues invalidate the failing
        shot-generation node and its evaluation/selection dependents, while
        keeping upstream character/scene references unless explicitly named.

        Args:
            issues: Discovered quality issues.
            graph: Current production graph.
            kind: Optional forced repair kind.

        Returns:
            RepairPlan with invalidate/keep sets and actions.
        """
        preflight_types = {
            IssueType.MISSING_INPUT,
            IssueType.MISSING_REFERENCE,
            IssueType.INCOMPLETE_SPEC,
            IssueType.INVALID_DEPENDENCY,
        }
        has_preflight = any(i.issue_type in preflight_types for i in issues)
        has_post = any(i.issue_type not in preflight_types for i in issues)
        resolved_kind = kind or (
            RepairKind.PREFLIGHT if has_preflight and not has_post else RepairKind.POST_GENERATION
        )

        plan = RepairPlan.create(
            kind=resolved_kind,
            rationale="minimal scope repair from structured issues",
        )
        plan.issues = [i.id for i in issues]

        seed_nodes: set[str] = set()
        for issue in issues:
            if issue.suggested_scope:
                seed_nodes.update(issue.suggested_scope)
            elif issue.node_id:
                seed_nodes.add(issue.node_id)

        if resolved_kind == RepairKind.PREFLIGHT:
            for node_id in seed_nodes:
                plan.add_invalidate(node_id, reason="preflight incomplete definition")
                plan.add_keep(node_id)  # keep identity, fix inputs
            return plan

        # Post-generation: expand to dependents of seed generation nodes
        expanded = set(seed_nodes)
        for seed in list(seed_nodes):
            for dependent in graph.dependents(seed):
                expanded.add(dependent)
            # also include generate_shot_candidates upstream of evaluate/select
            node = graph.nodes.get(seed)
            if node and node.action in (
                "evaluate_shot_candidates",
                "select_shot_candidate",
            ):
                for dep in graph.dependencies(seed):
                    dep_node = graph.nodes.get(dep)
                    if dep_node and dep_node.action == "generate_shot_candidates":
                        expanded.add(dep)

        for node_id in expanded:
            plan.add_invalidate(node_id, reason="affected by quality issue")

        # Keep character/scene reference nodes not in expanded set
        for node in graph.nodes.values():
            if node.action in (
                "build_character_reference",
                "generate_scene_reference",
            ) and node.id not in expanded:
                plan.add_keep(node.id)

        return plan

    def apply(self, plan: RepairPlan, graph: ProductionGraph) -> set[str]:
        """Apply repair plan to graph via dirty propagation.

        Args:
            plan: Repair plan.
            graph: Production graph to mutate.

        Returns:
            Set of invalidated node ids.
        """
        seeds = set(plan.invalidate_node_ids)
        invalidated = graph.invalidate_from(seeds)
        graph.reset_invalidated_to_pending()
        return invalidated

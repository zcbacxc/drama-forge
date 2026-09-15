# SPDX-FileCopyrightText: 2026 zcbacxc
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Programmatic entry point for Drama Forge Core Engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from drama_forge.artifacts.store import ArtifactStore
from drama_forge.compiler.parser import compile_story_from_dict, load_story_source
from drama_forge.compiler.production_spec import build_production_spec
from drama_forge.compiler.story_graph import (
    GraphPlanResult,
    build_production_graph,
    build_story_graph,
)
from drama_forge.domain.asset import Artifact, Candidate
from drama_forge.domain.common import ExecutionStatus, IssueType, RepairKind
from drama_forge.domain.knowledge import (
    ProductionKnowledge,
    harvest_knowledge_from_story,
)
from drama_forge.domain.production import ProductionManifest
from drama_forge.domain.quality import Issue, QualityResult, RepairPlan, ValidationReport
from drama_forge.domain.story import Story
from drama_forge.providers.factory import build_default_registry
from drama_forge.providers.registry import ProviderRegistry
from drama_forge.providers.router import ProviderRouter
from drama_forge.quality.repair import RepairPlanner
from drama_forge.quality.validators import validate_continuity
from drama_forge.runtime.checkpoint import CheckpointStore
from drama_forge.runtime.events import EventBus
from drama_forge.runtime.scheduler import (
    ExecutionContext,
    ExecutionPlan,
    Scheduler,
)
from drama_forge.runtime.worker import ProductionWorker


@dataclass(slots=True)
class RunResult:
    """Bundle returned by Engine.run()."""

    execution_id: str
    status: ExecutionStatus
    graph: Any
    context: ExecutionContext
    timeline_artifact: Artifact | None = None
    report: ValidationReport = field(default_factory=ValidationReport)
    knowledge: ProductionKnowledge | None = None

    @property
    def events(self) -> list[Any]:
        """Return execution events."""
        return self.context.events.list()

    def selected_candidates(self) -> list[Candidate]:
        """Return selected candidates from context."""
        return [
            c
            for c in self.context.candidates.values()
            if isinstance(c, Candidate) and c.selected
        ]

    def artifacts(self) -> list[Artifact]:
        """Return all artifacts produced in this run."""
        return list(self.context.artifacts.values())


class Engine:
    """Facade orchestrating compile → plan → run → quality → repair."""

    def __init__(
        self,
        artifact_root: str | Path | None = None,
        enable_mock_providers: bool = True,
        db_path: str | Path | None = None,
        env: dict[str, str] | None = None,
        registry: ProviderRegistry | None = None,
    ) -> None:
        """Create an Engine facade.

        Args:
            artifact_root: Filesystem root for artifact media bytes.
            enable_mock_providers: Register local mock providers.
            db_path: Optional SQLite path for durable production history.
            env: Optional environment mapping for provider factory.
            registry: Optional pre-built provider registry (overrides factory).
        """
        self.registry = registry or build_default_registry(
            env=env, enable_mock=enable_mock_providers
        )
        self.router = ProviderRouter(self.registry)
        self.artifact_store = ArtifactStore(artifact_root)
        self.checkpoint_store = CheckpointStore()
        self.repair_planner = RepairPlanner()
        self._executions: dict[str, RunResult] = {}
        self.fingerprint_cache: dict[str, dict[str, Any]] = {}
        self.db: Any | None = None
        self._repos: dict[str, Any] = {}
        if db_path is not None:
            self._init_persistence(db_path)

    def _init_persistence(self, db_path: str | Path) -> None:
        """Open SQLite database and prepare repositories."""
        from drama_forge.persistence import (
            ArtifactRepository,
            CandidateRepository,
            CheckpointRepository,
            Database,
            DecisionRepository,
            EventRepository,
            ExecutionRepository,
            GraphRepository,
            KnowledgeRepository,
            QualityRepository,
            RepairRepository,
            StoryRepository,
        )

        self.db = Database(str(db_path))
        self.db.migrate()
        self._repos = {
            "story": StoryRepository(self.db),
            "graph": GraphRepository(self.db),
            "execution": ExecutionRepository(self.db),
            "checkpoint": CheckpointRepository(self.db),
            "artifact": ArtifactRepository(self.db),
            "decision": DecisionRepository(self.db),
            "quality": QualityRepository(self.db),
            "repair": RepairRepository(self.db),
            "knowledge": KnowledgeRepository(self.db),
            "candidate": CandidateRepository(self.db),
            "event": EventRepository(self.db),
        }

    def compile(self, source: str | Path | dict[str, Any]) -> Story:
        """Compile a story source into a Story domain object."""
        if isinstance(source, dict):
            return compile_story_from_dict(source)
        return load_story_source(source)

    def plan(
        self,
        story: Story,
        candidate_count: int = 2,
        knowledge: ProductionKnowledge | None = None,
    ) -> tuple[ProductionManifest, GraphPlanResult, Any]:
        """Build production spec, manifest, and production graph.

        Args:
            story: Compiled story.
            candidate_count: Candidates per shot generation node.
            knowledge: Optional Production Knowledge merged into continuity
                constraints on generation specs.

        Returns:
            Tuple of (manifest, graph plan, story graph).
        """
        story_graph = build_story_graph(story)
        spec = build_production_spec(story)
        plan = build_production_graph(
            story, candidate_count=candidate_count, knowledge=knowledge
        )
        quality_policy: dict[str, Any] = {
            "enforce_continuity": True,
            "preflight": True,
        }
        if knowledge is not None:
            quality_policy["knowledge_fingerprint"] = knowledge.fingerprint
        manifest = ProductionManifest.create(
            story_id=story.id,
            story_version=story.version,
            production_spec_id=spec.id,
            graph_id=plan.graph.id,
            provider_policy={"strategy": "balanced"},
            selection_policy={"strategy": "highest_total_score"},
            quality_policy=quality_policy,
            asset_versions={aid: a.version for aid, a in plan.assets.items()},
        )
        errors = manifest.validate()
        if errors:
            raise ValueError(f"invalid production manifest: {errors}")
        return manifest, plan, story_graph

    def run(
        self,
        story: Story,
        candidate_count: int = 2,
        provider_policy: dict[str, Any] | None = None,
        resume_execution_id: str | None = None,
        inject_continuity_issue: bool = False,
        knowledge: ProductionKnowledge | None = None,
        max_workers: int = 1,
        cancellation: Any | None = None,
    ) -> RunResult:
        """Run the full production chain for a story.

        Args:
            story: Compiled story.
            candidate_count: Candidates per shot.
            provider_policy: Optional routing policy override.
            resume_execution_id: Resume from a previous execution checkpoint.
            inject_continuity_issue: Force a continuity failure for repair demos.
            knowledge: Optional Production Knowledge injected into continuity
                constraints of this run (not the story content itself).
            max_workers: Parallel workers for dependency-ready nodes.
            cancellation: Optional CancellationToken for cooperative cancel.

        Returns:
            RunResult with status, artifacts, timeline, quality report, knowledge.
        """
        manifest, plan, _story_graph = self.plan(
            story, candidate_count=candidate_count, knowledge=knowledge
        )
        graph = plan.graph
        policy = provider_policy or dict(manifest.provider_policy)

        if inject_continuity_issue:
            from drama_forge.providers.adapters import MockProvider

            # force low continuity scores on shot evaluation path
            policy = {**policy, "strategy": "quality_first"}
            # bias primary mock so first candidate digests produce low continuity
            for provider in self.registry.all():
                if isinstance(provider, MockProvider):
                    provider.quality_bias = -0.5

        resume_checkpoint = None
        if resume_execution_id:
            resume_checkpoint = self.checkpoint_store.load(resume_execution_id)

        execution_plan = ExecutionPlan.create(
            graph=graph,
            input_fingerprint=story.fingerprint(),
            config={
                "input_fingerprint": story.fingerprint(),
                "enable_fingerprint_reuse": True,
                "provider_policy": policy,
                "manifest_id": manifest.id,
            },
            provider_policy=policy,
        )
        context = ExecutionContext(
            execution_id=execution_plan.id,
            graph=graph,
            assets=plan.assets,
            events=EventBus(),
            config={
                "input_fingerprint": story.fingerprint(),
                "enable_fingerprint_reuse": resume_checkpoint is None,
                "provider_policy": policy,
                "manifest_id": manifest.id,
            },
        )
        worker = ProductionWorker(
            router=self.router,
            artifact_store=self.artifact_store,
            story_id=story.id,
            story_version=story.version,
        )
        scheduler = Scheduler(
            executor=worker,
            checkpoint_store=self.checkpoint_store,
            max_attempts=2,
            fingerprint_cache=self.fingerprint_cache,
            max_workers=max_workers,
        )
        if cancellation is not None:
            context.cancellation = cancellation
        status = scheduler.run(graph, context, resume_from=resume_checkpoint)

        timeline_id = context.config.get("canonical_timeline_id")
        timeline_artifact = (
            context.artifacts.get(timeline_id) if timeline_id else None
        )

        # Continuity quality pass over selected candidates
        selected = [
            c for c in context.candidates.values() if isinstance(c, Candidate) and c.selected
        ]
        character_ids_by_node: dict[str, list[str]] = {}
        for n in graph.nodes.values():
            if n.generation_spec:
                character_ids_by_node[n.id] = list(n.generation_spec.character_asset_ids)
        continuity_result = validate_continuity(
            graph, selected, character_ids_by_node=character_ids_by_node
        )
        report = ValidationReport()
        report.add(continuity_result)
        for qr in context.quality_results:
            if isinstance(qr, QualityResult) and qr is not continuity_result:
                report.add(qr)

        # If inject_continuity_issue, force at least one high severity issue
        if inject_continuity_issue and not any(
            i.issue_type == IssueType.CHARACTER_CONTINUITY for i in report.issues
        ):
            from drama_forge.domain.common import GateResult, Severity

            target = selected[0] if selected else None
            forced = Issue.create(
                IssueType.CHARACTER_CONTINUITY,
                Severity.HIGH,
                "injected continuity failure for repair demonstration",
                node_id=target.node_id if target else None,
                suggested_scope=[target.node_id] if target else [],
            )
            continuity_result.issues.append(forced)
            continuity_result.gate = GateResult.BLOCK
            report.issues.append(forced)

        result = RunResult(
            execution_id=context.execution_id,
            status=status,
            graph=graph,
            context=context,
            timeline_artifact=timeline_artifact,
            report=report,
            knowledge=self.harvest_knowledge(story, result=None, context=context, report=report),
        )
        self._executions[context.execution_id] = result
        self._persist_run_result(story, result)
        return result

    def harvest_knowledge(
        self,
        story: Story,
        result: RunResult | None = None,
        *,
        context: ExecutionContext | None = None,
        report: ValidationReport | None = None,
        previous: ProductionKnowledge | None = None,
    ) -> ProductionKnowledge:
        """Distill Production Knowledge from a completed (or partial) run.

        Args:
            story: Story that was produced.
            result: Optional RunResult (uses its context/report when present).
            context: Explicit execution context when result is None.
            report: Explicit validation report when result is None.
            previous: Optional prior knowledge bundle to merge into.

        Returns:
            Harvested (and optionally merged) ProductionKnowledge.
        """
        ctx = context or (result.context if result else None)
        rep = report or (result.report if result else None)
        selected: list[Any] = []
        decisions: list[Any] = []
        quality: list[Any] = []
        source_refs: list[str] = []
        if ctx is not None:
            selected = [
                c
                for c in ctx.candidates.values()
                if isinstance(c, Candidate) and c.selected
            ]
            decisions = list(ctx.decision_records)
            quality = list(ctx.quality_results)
            if ctx.execution_id:
                source_refs.append(ctx.execution_id)
            for artifact in list(ctx.artifacts.values())[:20]:
                aid = getattr(artifact, "id", None)
                if aid:
                    source_refs.append(str(aid))
        if rep is not None:
            quality.extend(list(rep.results))

        knowledge = harvest_knowledge_from_story(
            story,
            selected_candidates=selected,
            decision_records=decisions,
            quality_results=quality,
            source_refs=source_refs,
        )
        if previous is not None:
            knowledge = previous.merge(knowledge)
        if self._repos:
            try:
                repo = self._repos.get("knowledge")
                if repo is not None:
                    repo.save(knowledge)
            except Exception:  # noqa: BLE001 - knowledge persist is best-effort
                pass
        return knowledge

    def _persist_run_result(self, story: Story, result: RunResult) -> None:
        """Write production history into SQLite when persistence is enabled."""
        if not self._repos:
            return
        context = result.context
        graph = result.graph
        self._repos["story"].save(
            story.id,
            story.title,
            story.version,
            {
                "title": story.title,
                "fingerprint": story.fingerprint(),
                "character_count": len(story.characters),
                "shot_count": len(story.all_shots()),
            },
            fingerprint=story.fingerprint(),
        )
        self._repos["graph"].save_graph(
            graph.id,
            graph.name,
            graph.version,
            {
                nid: {
                    "name": n.name,
                    "action": n.action,
                    "status": n.status.value,
                    "fingerprint": n.fingerprint,
                }
                for nid, n in graph.nodes.items()
            },
            [
                {"source": e.source_id, "target": e.target_id, "kind": e.kind}
                for e in graph.edges
            ],
            fingerprint=graph.fingerprint(),
            policy=graph.policy,
        )
        self._repos["execution"].save(
            context.execution_id,
            graph.id,
            result.status.value,
            graph_fingerprint=graph.fingerprint(),
            input_fingerprint=str(context.config.get("input_fingerprint", "")),
            config={
                "provider_policy": context.config.get("provider_policy", {}),
            },
            result_summary={
                "artifact_count": len(context.artifacts),
                "decision_count": len(context.decision_records),
                "gate": result.report.overall_gate.value,
                "timeline_artifact_id": (
                    result.timeline_artifact.id if result.timeline_artifact else None
                ),
            },
        )
        cp = self.checkpoint_store.load(context.execution_id)
        if cp:
            self._repos["checkpoint"].save(cp)
        for artifact in context.artifacts.values():
            if isinstance(artifact, Artifact):
                self._repos["artifact"].save(
                    artifact.id,
                    artifact.artifact_type.value,
                    artifact.content_reference,
                    fingerprint=artifact.fingerprint(),
                    source_node=artifact.source_node,
                    asset_id=artifact.asset_id,
                    schema_version=artifact.schema_version,
                    technical_metadata=artifact.technical_metadata,
                    provider_metadata=artifact.provider_metadata,
                    generation_metadata=artifact.generation_metadata,
                    quality_state=artifact.quality_state.value,
                    provenance=artifact.provenance.to_dict(),
                    created_at=artifact.created_at,
                )
        for decision in context.decision_records:
            self._repos["decision"].save(
                decision.id,
                decision.decision_type,
                decision.subject,
                candidates=list(decision.candidates),
                policy=decision.policy,
                selected=decision.selected,
                reason=decision.reason,
                evidence=decision.evidence,
                execution_id=decision.execution_id,
                created_at=decision.created_at,
            )
        cand_repo = self._repos.get("candidate")
        if cand_repo is not None:
            for candidate in context.candidates.values():
                if not isinstance(candidate, Candidate):
                    continue
                artifact = getattr(candidate, "artifact", None)
                cand_repo.save(
                    candidate.id,
                    candidate.node_id,
                    artifact_id=getattr(artifact, "id", "") or "",
                    selected=bool(getattr(candidate, "selected", False)),
                    score=float(getattr(candidate, "score", 0.0) or 0.0),
                    quality_state=str(getattr(candidate, "quality_state", "UNEVALUATED")),
                    execution_id=context.execution_id,
                    payload={"artifact_type": str(getattr(artifact, "artifact_type", ""))},
                )
        event_repo = self._repos.get("event")
        if event_repo is not None:
            for event in context.events.list():
                event_repo.append(
                    context.execution_id,
                    event.event_type,
                    subject=event.subject,
                    payload=dict(event.payload),
                    created_at=event.created_at,
                )
        seen_qr: set[str] = set()
        for qr in list(context.quality_results) + list(result.report.results):
            if not isinstance(qr, QualityResult) or qr.id in seen_qr:
                continue
            seen_qr.add(qr.id)
            self._repos["quality"].save_result(
                qr.id,
                qr.subject_id,
                qr.gate.value,
                scores=qr.scores,
                evidence=qr.evidence,
                issues=[
                    {
                        "id": i.id,
                        "issue_type": i.issue_type.value,
                        "severity": i.severity.value,
                        "node_id": i.node_id,
                        "asset_id": i.asset_id,
                        "message": i.message,
                        "evidence": i.evidence,
                        "suggested_scope": i.suggested_scope,
                    }
                    for i in qr.issues
                ],
                created_at=qr.created_at,
            )

    def status(self, execution_id: str) -> dict[str, Any] | None:
        """Return execution status summary."""
        result = self._executions.get(execution_id)
        if result is None:
            cp = self.checkpoint_store.load(execution_id)
            if cp is None:
                return None
            return {
                "execution_id": execution_id,
                "status": cp.execution_status,
                "completed_nodes": cp.completed_nodes,
                "node_status": cp.node_status,
            }
        return {
            "execution_id": execution_id,
            "status": result.status.value,
            "node_status": {
                nid: n.status.value for nid, n in result.graph.nodes.items()
            },
            "artifact_count": len(result.context.artifacts),
            "decision_count": len(result.context.decision_records),
            "timeline_artifact_id": (
                result.timeline_artifact.id if result.timeline_artifact else None
            ),
            "gate": result.report.overall_gate.value,
        }

    def inspect(self, artifact_id: str) -> dict[str, Any] | None:
        """Trace provenance for an artifact."""
        return self.artifact_store.trace(artifact_id)

    def validate(self, execution_id: str) -> ValidationReport | None:
        """Return quality report for an execution."""
        result = self._executions.get(execution_id)
        return result.report if result else None

    def retry(self, execution_id: str, story: Story | None = None) -> RunResult:
        """Retry failed nodes of a prior execution without changing production definition.

        Distinct from repair: retry keeps the same generation specs and inputs
        and only re-executes nodes that previously failed (or their blocked
        dependents that are still pending).

        Args:
            execution_id: Prior execution to retry.
            story: Story used to rebuild execution context when needed.

        Returns:
            New RunResult after re-running failed scope.

        Raises:
            KeyError: If execution is unknown.
            ValueError: If no prior execution context is available and story is omitted.
        """
        from drama_forge.domain.common import NodeStatus

        prior = self._executions.get(execution_id)
        if prior is None:
            cp = self.checkpoint_store.load(execution_id)
            if cp is None:
                raise KeyError(f"unknown execution: {execution_id}")
            if story is None:
                raise ValueError(
                    "story is required to retry an execution not held in memory"
                )
            return self.run(story, resume_execution_id=execution_id)

        graph = prior.graph
        failed_nodes = [
            n for n in graph.nodes.values() if n.status == NodeStatus.FAILED
        ]
        for node in failed_nodes:
            node.status = NodeStatus.PENDING
            node.error = None
            node.attempt = 0

        # Also reset dependents that never ran because a dependency failed
        for node in graph.nodes.values():
            if node.status in (NodeStatus.PENDING, NodeStatus.BLOCKED):
                node.status = NodeStatus.PENDING

        if story is None:
            # Best-effort: re-run using stored config only if we can rebuild
            # from the same graph (production definition unchanged).
            raise ValueError("story is required to re-execute after retry reset")

        return self._run_graph(story, graph, dict(prior.context.config))

    def repair(
        self,
        execution_id: str,
        issues: list[Issue] | None = None,
        story: Story | None = None,
        kind: RepairKind | None = None,
    ) -> tuple[RepairPlan, RunResult]:
        """Plan and apply a local repair, then re-run affected scope.

        Args:
            execution_id: Prior execution to repair.
            issues: Optional explicit issues; defaults to last report issues.
            story: Story to re-run after repair.
            kind: Optional repair kind override.

        Returns:
            Tuple of (repair plan, new run result).

        Raises:
            KeyError: If execution is unknown.
            ValueError: If story is not provided for re-run.
        """
        prior = self._executions.get(execution_id)
        if prior is None:
            raise KeyError(f"unknown execution: {execution_id}")
        issue_list = issues if issues is not None else list(prior.report.issues)
        plan = self.repair_planner.plan(issue_list, prior.graph, kind=kind)
        invalidated = self.repair_planner.apply(plan, prior.graph)
        prior.context.events.emit(
            "repair.applied",
            execution_id,
            invalidated=sorted(invalidated),
            plan_id=plan.id,
        )

        if story is None:
            raise ValueError("story is required to re-run after repair")

        # Re-run using same story; graph was reset for invalidated nodes
        new_result = self._run_graph(story, prior.graph, prior.context.config)
        # merge repair history into provenance of new artifacts
        for artifact in new_result.context.artifacts.values():
            artifact.provenance.repair_history.append(plan.id)
        return plan, new_result

    def _run_graph(
        self,
        story: Story,
        graph: Any,
        config: dict[str, Any],
    ) -> RunResult:
        """Execute an already-built graph (used by repair re-runs)."""
        policy = dict(config.get("provider_policy", {}))
        execution_plan = ExecutionPlan.create(
            graph=graph,
            input_fingerprint=story.fingerprint(),
            config={
                "input_fingerprint": story.fingerprint(),
                "enable_fingerprint_reuse": False,
                "provider_policy": policy,
            },
            provider_policy=policy,
        )
        context = ExecutionContext(
            execution_id=execution_plan.id,
            graph=graph,
            events=EventBus(),
            config={
                "input_fingerprint": story.fingerprint(),
                "enable_fingerprint_reuse": False,
                "provider_policy": policy,
            },
        )
        # Rehydrate assets from prior if needed 鈥?assets live on graph specs
        worker = ProductionWorker(
            router=self.router,
            artifact_store=self.artifact_store,
            story_id=story.id,
            story_version=story.version,
        )
        scheduler = Scheduler(
            executor=worker,
            checkpoint_store=self.checkpoint_store,
            max_attempts=2,
            fingerprint_cache=self.fingerprint_cache,
        )
        status = scheduler.run(graph, context)

        timeline_id = context.config.get("canonical_timeline_id")
        timeline_artifact = (
            context.artifacts.get(timeline_id) if timeline_id else None
        )
        selected = [
            c for c in context.candidates.values() if isinstance(c, Candidate) and c.selected
        ]
        character_ids_by_node: dict[str, list[str]] = {}
        for n in graph.nodes.values():
            if n.generation_spec:
                character_ids_by_node[n.id] = list(n.generation_spec.character_asset_ids)
        continuity_result = validate_continuity(
            graph, selected, character_ids_by_node=character_ids_by_node
        )
        report = ValidationReport()
        report.add(continuity_result)

        result = RunResult(
            execution_id=context.execution_id,
            status=status,
            graph=graph,
            context=context,
            timeline_artifact=timeline_artifact,
            report=report,
        )
        self._executions[context.execution_id] = result
        return result

    def update_timeline_shot(
        self,
        execution_id: str,
        segment_node_name: str,
        new_artifact: Artifact,
    ) -> Artifact:
        """Replace one shot in the canonical timeline without full rebuild.

        Args:
            execution_id: Execution owning the timeline.
            segment_node_name: Select-node name whose segment to replace.
            new_artifact: Replacement artifact.

        Returns:
            Updated timeline artifact.

        Raises:
            KeyError: If execution or timeline is missing.
            ValueError: If segment is not found.
        """
        result = self._executions.get(execution_id)
        if result is None or result.timeline_artifact is None:
            raise KeyError(f"no timeline for execution {execution_id}")
        payload = dict(result.timeline_artifact.generation_metadata)
        tracks = dict(payload.get("tracks", {}))
        video = list(tracks.get("video", []))
        updated = False
        for segment in video:
            node = result.graph.nodes.get(str(segment.get("node_id")))
            if node and (node.name == segment_node_name or node.id == segment_node_name):
                segment["artifact_id"] = new_artifact.id
                segment["digest"] = new_artifact.generation_metadata.get("digest")
                segment["replaced"] = True
                updated = True
                break
        if not updated:
            raise ValueError(f"segment not found: {segment_node_name}")
        tracks["video"] = video
        payload["tracks"] = tracks
        payload["metadata"] = {
            **payload.get("metadata", {}),
            "last_replaced_segment": segment_node_name,
        }
        result.timeline_artifact.generation_metadata = payload
        self.artifact_store.put(
            result.timeline_artifact,
            content=__import__("json").dumps(payload, indent=2),
        )
        return result.timeline_artifact

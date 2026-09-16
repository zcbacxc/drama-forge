# SPDX-FileCopyrightText: 2026 zcbacxc
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Node worker that executes production nodes via providers + artifacts."""

from __future__ import annotations

import json
from typing import Any

from drama_forge.artifacts.store import ArtifactStore
from drama_forge.domain.asset import Artifact, Candidate, CandidateSet, Provenance
from drama_forge.domain.common import ArtifactType, FailureClass
from drama_forge.domain.production import DecisionRecord, GraphNode
from drama_forge.providers.base import ProviderRequest, ProviderResponse
from drama_forge.providers.router import ProviderRouter
from drama_forge.quality.evaluators import evaluate_candidates, parse_evaluation_json
from drama_forge.quality.validators import validate_artifact
from drama_forge.runtime.scheduler import ExecutionContext, TaskResult


class ProductionWorker:
    """Execute production graph nodes against capability providers."""

    def __init__(
        self,
        router: ProviderRouter,
        artifact_store: ArtifactStore,
        story_id: str = "",
        story_version: int = 1,
    ) -> None:
        """__init__.

        Args:
                    router: ProviderRouter
                    artifact_store: ArtifactStore
                    story_id: default ''
                    story_version: default 1
        """
        self.router = router
        self.artifact_store = artifact_store
        self.story_id = story_id
        self.story_version = story_version

    def execute(self, node: GraphNode, context: ExecutionContext) -> TaskResult:
        """Dispatch node by action name.

        Args:
            node: Graph node to execute.
            context: Shared execution context.

        Returns:
            TaskResult describing success/failure and produced ids.
        """
        action = node.action
        handlers = {
            "build_character_reference": self._generate_reference,
            "generate_scene_reference": self._generate_reference,
            "generate_shot_candidates": self._generate_shot_candidates,
            "evaluate_shot_candidates": self._evaluate_candidates,
            "select_shot_candidate": self._select_candidate,
            "generate_dialogue_audio": self._generate_dialogue_audio,
            "assemble_timeline": self._assemble_timeline,
            "validate_continuity": self._validate_continuity,
        }
        handler = handlers.get(action)
        if handler is None:
            return TaskResult(
                node_id=node.id,
                success=False,
                error=f"unknown action: {action}",
            )
        return handler(node, context)

    def _route(
        self,
        node: GraphNode,
        context: ExecutionContext,
        capability: str,
    ) -> tuple[Any, DecisionRecord]:
        """Route to a provider using node/generation policy."""
        policy = dict(context.config.get("provider_policy", {}))
        if node.policy:
            policy.update(node.policy)
        provider, decision = self.router.select(
            capability=capability,
            policy=policy,
            subject=node.name,
            execution_id=context.execution_id,
        )
        context.decision_records.append(decision)
        context.events.emit(
            "provider.selected",
            node.id,
            provider=provider.id,
            capability=capability,
        )
        return provider, decision

    @staticmethod
    def _provider_failure(
        node: GraphNode,
        response: ProviderResponse,
        **extra: Any,
    ) -> TaskResult:
        """Map a failed ProviderResponse to a HARD TaskResult.

        Preserves ``response.retryable`` so the Scheduler can distinguish
        transient failures (backoff retry) from permanent ones (FAILED).
        """
        return TaskResult(
            node_id=node.id,
            success=False,
            error=response.error,
            failure_class=FailureClass.HARD_FAILURE,
            retryable=bool(response.retryable),
            **extra,
        )

    def _provenance(
        self,
        node: GraphNode,
        context: ExecutionContext,
        provider_id: str,
        model_id: str,
        candidate_id: str | None = None,
    ) -> Provenance:
        """Build provenance for a new artifact."""
        return Provenance(
            story_id=self.story_id,
            story_version=self.story_version,
            asset_ids=list(node.input_asset_ids)
            + ([node.output_asset_id] if node.output_asset_id else []),
            graph_node_id=node.id,
            execution_id=context.execution_id,
            generation_spec_hash=(
                node.generation_spec.fingerprint() if node.generation_spec else None
            ),
            provider_id=provider_id,
            model_id=model_id,
            candidate_id=candidate_id,
            inputs={
                "action": node.action,
                "name": node.name,
            },
        )

    def _generate_reference(
        self,
        node: GraphNode,
        context: ExecutionContext,
    ) -> TaskResult:
        """Generate a single reference artifact (character/scene)."""
        if node.generation_spec is None:
            return TaskResult(node_id=node.id, success=False, error="missing generation_spec")
        provider, _decision = self._route(
            node, context, node.generation_spec.capability
        )
        request = ProviderRequest(
            capability=node.generation_spec.capability,
            generation_spec=node.generation_spec,
            inputs={"asset_ids": node.input_asset_ids},
            policy=dict(context.config.get("provider_policy", {})),
            candidate_index=0,
        )
        response = provider.generate(request)
        if not response.ok:
            return self._provider_failure(node, response)

        artifact = Artifact.create(
            artifact_type=ArtifactType.IMAGE
            if "image" in node.generation_spec.capability
            else ArtifactType.JSON,
            content_reference="",
            source_node=node.id,
            asset_id=node.output_asset_id,
            technical_metadata=dict(response.technical_metadata),
            provider_metadata=dict(response.provider_metadata),
            generation_metadata=dict(response.generation_metadata),
        )
        artifact.provenance = self._provenance(
            node,
            context,
            provider_id=provider.id,
            model_id=str(response.provider_metadata.get("model", provider.id)),
        )
        self.artifact_store.put(artifact, content=response.content)
        context.artifacts[artifact.id] = artifact
        validation = validate_artifact(artifact)
        context.quality_results.append(validation)
        if validation.gate.value == "BLOCK":
            return TaskResult(
                node_id=node.id,
                success=False,
                error="artifact failed technical validation",
                artifact_ids=[artifact.id],
            )
        return TaskResult(
            node_id=node.id,
            success=True,
            artifact_ids=[artifact.id],
            output_fingerprints={"artifact": artifact.fingerprint()},
            outputs={"digest": response.generation_metadata.get("digest")},
        )

    def _generate_shot_candidates(
        self,
        node: GraphNode,
        context: ExecutionContext,
    ) -> TaskResult:
        """Generate N candidates for a shot."""
        if node.generation_spec is None:
            return TaskResult(node_id=node.id, success=False, error="missing generation_spec")
        provider, _decision = self._route(
            node, context, node.generation_spec.capability
        )
        candidate_set = CandidateSet(node_id=node.id)
        count = max(1, int(node.generation_spec.candidate_count))
        artifact_ids: list[str] = []
        candidate_ids: list[str] = []
        digests: list[str] = []

        for index in range(count):
            request = ProviderRequest(
                capability=node.generation_spec.capability,
                generation_spec=node.generation_spec,
                inputs={"asset_ids": node.input_asset_ids},
                policy=dict(context.config.get("provider_policy", {})),
                candidate_index=index,
            )
            response = provider.generate(request)
            if not response.ok:
                return self._provider_failure(
                    node,
                    response,
                    artifact_ids=artifact_ids,
                    candidate_ids=candidate_ids,
                )
            artifact = Artifact.create(
                artifact_type=ArtifactType.VIDEO
                if "video" in node.generation_spec.capability
                else ArtifactType.IMAGE,
                content_reference="",
                source_node=node.id,
                asset_id=node.output_asset_id,
                technical_metadata=dict(response.technical_metadata),
                provider_metadata=dict(response.provider_metadata),
                generation_metadata=dict(response.generation_metadata),
            )
            candidate = Candidate.create(node_id=node.id, artifact=artifact)
            artifact.provenance = self._provenance(
                node,
                context,
                provider_id=provider.id,
                model_id=str(response.provider_metadata.get("model", provider.id)),
                candidate_id=candidate.id,
            )
            self.artifact_store.put(artifact, content=response.content)
            context.artifacts[artifact.id] = artifact
            context.candidates[candidate.id] = candidate
            candidate_set.add(candidate)
            artifact_ids.append(artifact.id)
            candidate_ids.append(candidate.id)
            digests.append(str(response.generation_metadata.get("digest", "")))

        context.candidates[f"set:{node.id}"] = candidate_set
        return TaskResult(
            node_id=node.id,
            success=True,
            artifact_ids=artifact_ids,
            candidate_ids=candidate_ids,
            output_fingerprints={
                cid: context.candidates[cid].artifact.fingerprint() for cid in candidate_ids
            },
            outputs={"digests": digests, "candidate_count": count},
        )

    def _evaluate_candidates(
        self,
        node: GraphNode,
        context: ExecutionContext,
    ) -> TaskResult:
        """Evaluate candidates from the upstream generation node."""
        deps = context.graph.dependencies(node.id)
        gen_node_id = next(
            (
                d
                for d in deps
                if context.graph.nodes[d].action == "generate_shot_candidates"
            ),
            None,
        )
        if gen_node_id is None:
            return TaskResult(
                node_id=node.id,
                success=False,
                error="no upstream generate_shot_candidates node",
            )
        gen_node = context.graph.nodes[gen_node_id]
        candidate_ids = list(gen_node.candidate_ids)
        candidate_set = CandidateSet(node_id=gen_node_id)
        digests: list[str] = []
        for cid in candidate_ids:
            candidate = context.candidates.get(cid)
            if candidate is None:
                continue
            candidate_set.add(candidate)
            digests.append(
                str(candidate.artifact.generation_metadata.get("digest", ""))
            )

        capability = "vision_evaluation"
        if node.generation_spec and node.generation_spec.capability:
            capability = node.generation_spec.capability
        provider, _decision = self._route(node, context, capability)

        if node.generation_spec is None:
            return TaskResult(node_id=node.id, success=False, error="missing generation_spec")
        request = ProviderRequest(
            capability=capability,
            generation_spec=node.generation_spec,
            inputs={
                "candidate_digests": digests,
                "candidate_ids": candidate_ids,
            },
            policy={},
            candidate_index=0,
        )
        response = provider.generate(request)
        if not response.ok:
            return self._provider_failure(node, response)

        payload = parse_evaluation_json(response.content)
        result = evaluate_candidates(candidate_set, payload)
        context.quality_results.append(result)

        eval_artifact = Artifact.create(
            artifact_type=ArtifactType.EVALUATION,
            content_reference="",
            source_node=node.id,
            technical_metadata=dict(response.technical_metadata),
            provider_metadata=dict(response.provider_metadata),
            generation_metadata={
                "node": gen_node_id,
                "scores": payload.get("scores", []),
            },
        )
        eval_artifact.provenance = self._provenance(
            node,
            context,
            provider_id=provider.id,
            model_id=str(response.provider_metadata.get("model", provider.id)),
        )
        self.artifact_store.put(eval_artifact, content=response.content)
        context.artifacts[eval_artifact.id] = eval_artifact

        return TaskResult(
            node_id=node.id,
            success=True,
            artifact_ids=[eval_artifact.id],
            candidate_ids=candidate_ids,
            outputs={
                "evaluation": payload,
                "ranked": [c.id for c in candidate_set.rank()],
            },
        )

    def _select_candidate(
        self,
        node: GraphNode,
        context: ExecutionContext,
    ) -> TaskResult:
        """Select canonical candidate from upstream evaluation."""
        deps = context.graph.dependencies(node.id)
        eval_node_id = next(
            (
                d
                for d in deps
                if context.graph.nodes[d].action == "evaluate_shot_candidates"
            ),
            None,
        )
        if eval_node_id is None:
            return TaskResult(
                node_id=node.id,
                success=False,
                error="no upstream evaluate node",
            )
        eval_node = context.graph.nodes[eval_node_id]
        candidate_ids = list(eval_node.candidate_ids)
        candidate_set = CandidateSet(node_id=eval_node_id)
        for cid in candidate_ids:
            candidate = context.candidates.get(cid)
            if candidate:
                candidate_set.add(candidate)

        selected = candidate_set.select()
        if selected is None:
            return TaskResult(
                node_id=node.id,
                success=False,
                error="no candidates available for selection",
            )

        decision = DecisionRecord.create(
            decision_type="candidate_selection",
            subject=node.name,
            candidates=[c.id for c in candidate_set.candidates],
            policy={"strategy": "highest_total_score"},
            selected=selected.id,
            reason=f"total_score={selected.total_score:.4f}",
            evidence={
                "scores": {c.id: c.total_score for c in candidate_set.candidates}
            },
            execution_id=context.execution_id,
        )
        context.decision_records.append(decision)
        context.candidates[f"selected:{node.id}"] = selected

        # Mirror selected artifact ids on this node for timeline assembly
        node.artifact_ids = [selected.artifact.id]
        node.candidate_ids = [selected.id]

        return TaskResult(
            node_id=node.id,
            success=True,
            artifact_ids=[selected.artifact.id],
            candidate_ids=[selected.id],
            outputs={"selected_candidate": selected.id},
        )

    def _generate_dialogue_audio(
        self,
        node: GraphNode,
        context: ExecutionContext,
    ) -> TaskResult:
        """Generate dialogue audio for a shot after candidate selection."""
        if node.generation_spec is None:
            return TaskResult(node_id=node.id, success=False, error="missing generation_spec")
        capability = node.generation_spec.capability or "audio_generation"
        provider, _decision = self._route(node, context, capability)
        request = ProviderRequest(
            capability=capability,
            generation_spec=node.generation_spec,
            inputs={
                "asset_ids": node.input_asset_ids,
                **dict(node.generation_spec.audio_requirements),
            },
            policy=dict(context.config.get("provider_policy", {})),
            candidate_index=0,
        )
        response = provider.generate(request)
        if not response.ok:
            return self._provider_failure(node, response)

        artifact = Artifact.create(
            artifact_type=ArtifactType.AUDIO,
            content_reference="",
            source_node=node.id,
            asset_id=node.output_asset_id,
            technical_metadata=dict(response.technical_metadata),
            provider_metadata=dict(response.provider_metadata),
            generation_metadata=dict(response.generation_metadata),
        )
        requirements = dict(node.generation_spec.audio_requirements)
        artifact.generation_metadata["duration_seconds"] = float(
            requirements.get("duration_seconds", 2.0) or 2.0
        )
        artifact.generation_metadata["dialogue_text"] = str(
            requirements.get("text", "")
        )
        artifact.provenance = self._provenance(
            node,
            context,
            provider_id=provider.id,
            model_id=str(response.provider_metadata.get("model", provider.id)),
        )
        self.artifact_store.put(artifact, content=response.content)
        context.artifacts[artifact.id] = artifact
        validation = validate_artifact(artifact)
        context.quality_results.append(validation)
        if validation.gate.value == "BLOCK":
            return TaskResult(
                node_id=node.id,
                success=False,
                error="dialogue audio failed technical validation",
                artifact_ids=[artifact.id],
            )
        return TaskResult(
            node_id=node.id,
            success=True,
            artifact_ids=[artifact.id],
            output_fingerprints={"artifact": artifact.fingerprint()},
            outputs={
                "digest": response.generation_metadata.get("digest"),
                "duration_seconds": artifact.generation_metadata["duration_seconds"],
            },
        )

    def _assemble_timeline(
        self,
        node: GraphNode,
        context: ExecutionContext,
    ) -> TaskResult:
        """Assemble canonical timeline from selected shot artifacts.

        Uses TimelineRenderer to resolve segment order, compute start/end
        times, and align dialogue audio to its host video segment.
        """
        from drama_forge.timeline.renderer import CanonicalTimelineBuilder, TimelineRenderer

        select_nodes = [
            n
            for n in context.graph.nodes.values()
            if n.action == "select_shot_candidate"
        ]
        audio_nodes = [
            n
            for n in context.graph.nodes.values()
            if n.action == "generate_dialogue_audio"
        ]

        builder = CanonicalTimelineBuilder()
        timeline = builder.build_from_execution(
            select_nodes=select_nodes,
            audio_nodes=audio_nodes,
            candidates=context.candidates,
            artifacts=context.artifacts,
            name=node.name,
        )

        if not timeline.video_segments():
            return TaskResult(
                node_id=node.id,
                success=False,
                error="no selected shot segments for timeline",
            )

        rendered = TimelineRenderer().render(timeline)

        # Keep payload shape compatible with engine.update_timeline_shot while
        # also exposing resolved times and the audio track.
        video_segments = []
        for segment in timeline.video_segments():
            video_segments.append(
                {
                    "node_id": segment.node_id or segment.node_name,
                    "node_name": segment.node_name,
                    "artifact_id": segment.artifact_id,
                    "candidate_id": segment.candidate_id,
                    "duration_seconds": segment.duration_seconds,
                    "start_seconds": segment.start_seconds,
                    "end_seconds": segment.end_seconds,
                    "media": segment.media,
                    "digest": segment.digest,
                    "replaced": segment.replaced,
                }
            )
        audio_segments = [
            s.to_dict() for s in timeline.audio_segments()
        ]

        timeline_payload = {
            "tracks": {
                "video": video_segments,
                "audio": audio_segments,
            },
            "dialogues": [d.to_dict() for d in timeline.dialogues],
            "transitions": [t.to_dict() for t in timeline.transitions],
            "markers": [m.to_dict() for m in timeline.markers],
            "segment_order": list(rendered.segment_order),
            "audio_alignment": list(rendered.audio_alignment),
            "metadata": {
                "segment_count": len(video_segments),
                "audio_segment_count": len(audio_segments),
                "total_duration": rendered.total_duration,
            },
        }
        timeline_artifact = Artifact.create(
            artifact_type=ArtifactType.TIMELINE,
            content_reference="",
            source_node=node.id,
            asset_id=node.output_asset_id,
            technical_metadata={
                "segment_count": len(video_segments),
                "total_duration": rendered.total_duration,
            },
            generation_metadata=timeline_payload,
        )
        timeline_artifact.provenance = self._provenance(
            node,
            context,
            provider_id="internal-timeline",
            model_id="timeline-renderer",
            candidate_id=None,
        )
        timeline_artifact.provenance.inputs["segments"] = json.dumps(
            [s["artifact_id"] for s in video_segments]
        )
        self.artifact_store.put(
            timeline_artifact,
            content=timeline.to_json(),
        )
        context.artifacts[timeline_artifact.id] = timeline_artifact
        context.config["canonical_timeline_id"] = timeline_artifact.id
        context.config["canonical_timeline"] = timeline

        return TaskResult(
            node_id=node.id,
            success=True,
            artifact_ids=[timeline_artifact.id],
            outputs={
                "timeline": timeline_payload,
                "total_duration": rendered.total_duration,
            },
        )

    def _validate_continuity(
        self,
        node: GraphNode,
        context: ExecutionContext,
    ) -> TaskResult:
        """Validate continuity over selected candidates."""
        from drama_forge.quality.validators import validate_continuity

        selected = [
            c
            for c in context.candidates.values()
            if isinstance(c, Candidate) and c.selected
        ]
        character_ids_by_node: dict[str, list[str]] = {}
        for n in context.graph.nodes.values():
            if n.generation_spec:
                character_ids_by_node[n.id] = list(
                    n.generation_spec.character_asset_ids
                )

        result = validate_continuity(
            context.graph, selected, character_ids_by_node=character_ids_by_node
        )
        context.quality_results.append(result)

        report_artifact = Artifact.create(
            artifact_type=ArtifactType.EVALUATION,
            content_reference="",
            source_node=node.id,
            technical_metadata={"gate": result.gate.value},
            generation_metadata={
                "gate": result.gate.value,
                "issue_count": len(result.issues),
                "issues": [
                    {
                        "id": i.id,
                        "type": i.issue_type.value,
                        "severity": i.severity.value,
                        "node_id": i.node_id,
                        "message": i.message,
                    }
                    for i in result.issues
                ],
            },
        )
        report_artifact.provenance = self._provenance(
            node,
            context,
            provider_id="internal-quality",
            model_id="continuity-validator",
        )
        self.artifact_store.put(
            report_artifact,
            content=json.dumps(result.evidence, indent=2, default=str),
        )
        context.artifacts[report_artifact.id] = report_artifact

        if result.gate.value == "BLOCK":
            # Still succeed the node so execution completes; issues drive repair.
            return TaskResult(
                node_id=node.id,
                success=True,
                artifact_ids=[report_artifact.id],
                outputs={"gate": result.gate.value, "blocked": True},
            )
        return TaskResult(
            node_id=node.id,
            success=True,
            artifact_ids=[report_artifact.id],
            outputs={"gate": result.gate.value},
        )

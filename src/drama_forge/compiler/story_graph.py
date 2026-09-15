# SPDX-FileCopyrightText: 2026 zcbacxc
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Build Story Graph and Production Graph from a Story."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from drama_forge.domain.asset import Asset
from drama_forge.domain.production import (
    CanonicalGenerationSpec,
    GraphEdge,
    GraphNode,
    ProductionGraph,
)
from drama_forge.domain.story import Story


@dataclass(slots=True)
class StoryGraph:
    """Story relationship graph (content relations, not execution)."""

    nodes: dict[str, dict[str, Any]] = field(default_factory=dict)
    edges: list[tuple[str, str, str]] = field(default_factory=list)

    def add_node(self, entity_id: str, kind: str, name: str = "") -> None:
        """Register a story entity node."""
        self.nodes[entity_id] = {"kind": kind, "name": name}

    def add_edge(self, source_id: str, target_id: str, kind: str) -> None:
        """Register a story relationship edge."""
        self.edges.append((source_id, target_id, kind))


def build_story_graph(story: Story) -> StoryGraph:
    """Build a story relationship graph from content objects.

    Edges include appears_in, interacts_with, participates_in, shot_of.

    Args:
        story: Source story.

    Returns:
        StoryGraph with entities and relations.
    """
    graph = StoryGraph()
    graph.add_node(story.id, "story", story.title)
    for character in story.characters.values():
        graph.add_node(character.id, "character", character.name)
    for prop in story.props.values():
        graph.add_node(prop.id, "prop", prop.name)

    for episode in story.episodes:
        graph.add_node(episode.id, "episode", episode.title)
        graph.add_edge(episode.id, story.id, "episode_of")
        for scene in episode.scenes:
            graph.add_node(scene.id, "scene", scene.location)
            graph.add_edge(scene.id, episode.id, "scene_of")
            for char_id in scene.character_ids:
                if char_id in story.characters:
                    graph.add_edge(char_id, scene.id, "appears_in")
            for shot in scene.shots:
                graph.add_node(shot.id, "shot", shot.description[:40])
                graph.add_edge(shot.id, scene.id, "shot_of")
                for char_id in shot.character_ids:
                    if char_id in story.characters:
                        graph.add_edge(char_id, shot.id, "appears_in")

    char_ids = list(story.characters.keys())
    for i, a in enumerate(char_ids):
        for b in char_ids[i + 1 :]:
            graph.add_edge(a, b, "interacts_with")

    for event in story.events:
        graph.add_node(event.id, "event", event.description[:40])
        for char_id in event.character_ids:
            graph.add_edge(char_id, event.id, "participates_in")

    for rel in story.relationships:
        graph.add_edge(rel.source_id, rel.target_id, rel.kind)
    return graph


@dataclass(slots=True)
class GraphPlanResult:
    """Result of planning a production graph with associated assets."""

    graph: ProductionGraph
    assets: dict[str, Asset] = field(default_factory=dict)


def build_production_graph(
    story: Story,
    name: str | None = None,
    style_constraints: dict[str, Any] | None = None,
    candidate_count: int = 2,
) -> GraphPlanResult:
    """Plan a production graph from a story.

    Reference production chain:
    character_reference -> scene_reference -> shot_candidates ->
    evaluate -> select -> assemble_timeline -> validate_continuity

    Args:
        story: Compiled story.
        name: Optional graph name.
        style_constraints: Global style constraints.
        candidate_count: Candidates per shot generation node.

    Returns:
        GraphPlanResult containing graph and created assets.
    """
    style_constraints = style_constraints or (
        {"style": story.world.style} if story.world and story.world.style else {}
    )
    graph = ProductionGraph.create(name=name or f"{story.title}-production")
    assets: dict[str, Asset] = {}

    # Character reference assets + nodes
    char_ref_nodes: dict[str, GraphNode] = {}
    for character in story.characters.values():
        asset = Asset.create(
            kind="character_reference",
            name=character.name,
            subject_id=character.id,
            constraints={
                "appearance": character.appearance,
                "personality": character.personality,
                "voice_identity": character.voice_identity,
                "costume_state": character.costume_state,
            },
        )
        assets[asset.id] = asset
        node = GraphNode.create(
            name=f"character_ref:{character.name}",
            action="build_character_reference",
            input_asset_ids=[],
            output_asset_id=asset.id,
        )
        node.generation_spec = CanonicalGenerationSpec(
            node_id=node.id,
            capability="image_generation",
            character_asset_ids=[asset.id],
            style_constraints=style_constraints,
            continuity_constraints={"subject": character.name},
            output_requirements={"aspect_ratio": "1:1", "media": "image"},
            candidate_count=1,
        )
        graph.add_node(node)
        char_ref_nodes[character.id] = node

    # Scene reference assets + nodes
    scene_ref_nodes: dict[str, GraphNode] = {}
    for episode in story.episodes:
        for scene in episode.scenes:
            asset = Asset.create(
                kind="scene_reference",
                name=scene.location or f"scene-{scene.index}",
                subject_id=scene.id,
                constraints={"location": scene.location, "description": scene.description},
            )
            assets[asset.id] = asset
            node = GraphNode.create(
                name=f"scene_ref:{scene.index}",
                action="generate_scene_reference",
                output_asset_id=asset.id,
            )
            # depend on character refs present in scene
            node.input_asset_ids = [
                assets[next(a.id for a in assets.values() if a.subject_id == cid)].id
                for cid in scene.character_ids
                if any(a.subject_id == cid for a in assets.values())
            ]
            for cid in scene.character_ids:
                dep = char_ref_nodes.get(cid)
                if dep:
                    graph.add_edge(GraphEdge.create(dep.id, node.id))
            node.generation_spec = CanonicalGenerationSpec(
                node_id=node.id,
                capability="image_generation",
                character_asset_ids=list(node.input_asset_ids),
                location_asset_id=asset.id,
                style_constraints=style_constraints,
                output_requirements={"aspect_ratio": "16:9", "media": "image"},
                candidate_count=1,
            )
            graph.add_node(node)
            scene_ref_nodes[scene.id] = node

            # Shot generation / evaluate / select
            for shot in scene.shots:
                shot_asset = Asset.create(
                    kind="shot_spec",
                    name=f"shot-{scene.index}.{shot.index}",
                    subject_id=shot.id,
                    constraints={
                        "description": shot.description,
                        "dialogue": shot.dialogue,
                        "duration_seconds": shot.duration_seconds,
                        "camera": shot.camera,
                    },
                )
                assets[shot_asset.id] = shot_asset

                gen_node = GraphNode.create(
                    name=f"shot_gen:{scene.index}.{shot.index}",
                    action="generate_shot_candidates",
                    output_asset_id=shot_asset.id,
                    input_asset_ids=[asset.id, *node.input_asset_ids],
                )
                graph.add_edge(GraphEdge.create(node.id, gen_node.id))
                for cid in shot.character_ids:
                    dep = char_ref_nodes.get(cid)
                    if dep:
                        graph.add_edge(GraphEdge.create(dep.id, gen_node.id))
                gen_node.generation_spec = CanonicalGenerationSpec(
                    node_id=gen_node.id,
                    capability="video_generation",
                    character_asset_ids=list(node.input_asset_ids),
                    location_asset_id=asset.id,
                    style_constraints=style_constraints,
                    continuity_constraints={
                        "characters": shot.character_ids,
                        "scene": scene.id,
                    },
                    camera_spec={"camera": shot.camera},
                    output_requirements={
                        "media": "video",
                        "duration_seconds": shot.duration_seconds,
                    },
                    candidate_count=candidate_count,
                )
                graph.add_node(gen_node)

                eval_node = GraphNode.create(
                    name=f"shot_eval:{scene.index}.{shot.index}",
                    action="evaluate_shot_candidates",
                    input_asset_ids=[shot_asset.id],
                    generation_spec=CanonicalGenerationSpec(
                        node_id=new_eval_id(),
                        capability="vision_evaluation",
                        inputs={"node": gen_node.id},
                        continuity_constraints={
                            "characters": shot.character_ids,
                        },
                    ),
                )
                # fix node_id in spec
                assert eval_node.generation_spec is not None
                eval_node.generation_spec.node_id = eval_node.id
                graph.add_edge(GraphEdge.create(gen_node.id, eval_node.id))
                graph.add_node(eval_node)

                select_node = GraphNode.create(
                    name=f"shot_select:{scene.index}.{shot.index}",
                    action="select_shot_candidate",
                    input_asset_ids=[shot_asset.id],
                    generation_spec=CanonicalGenerationSpec(
                        node_id="pending",
                        capability="selection",
                        selection_policy={"strategy": "highest_total_score"},
                    ),
                )
                assert select_node.generation_spec is not None
                select_node.generation_spec.node_id = select_node.id
                graph.add_edge(GraphEdge.create(eval_node.id, select_node.id))
                graph.add_node(select_node)

    # Timeline assembly
    timeline_asset = Asset.create(kind="timeline", name=f"{story.title}-timeline")
    assets[timeline_asset.id] = timeline_asset
    timeline_node = GraphNode.create(
        name="assemble_timeline",
        action="assemble_timeline",
        output_asset_id=timeline_asset.id,
        generation_spec=CanonicalGenerationSpec(
            node_id="pending",
            capability="timeline_assembly",
            output_requirements={"media": "timeline"},
        ),
    )
    assert timeline_node.generation_spec is not None
    timeline_node.generation_spec.node_id = timeline_node.id
    graph.add_node(timeline_node)
    select_nodes = [n for n in graph.nodes.values() if n.action == "select_shot_candidate"]
    for select_node in select_nodes:
        graph.add_edge(GraphEdge.create(select_node.id, timeline_node.id))

    # Continuity validation
    continuity_node = GraphNode.create(
        name="validate_continuity",
        action="validate_continuity",
        input_asset_ids=[timeline_asset.id],
        generation_spec=CanonicalGenerationSpec(
            node_id="pending",
            capability="continuity_validation",
        ),
    )
    assert continuity_node.generation_spec is not None
    continuity_node.generation_spec.node_id = continuity_node.id
    graph.add_edge(GraphEdge.create(timeline_node.id, continuity_node.id))
    graph.add_node(continuity_node)

    # Dialogue audio nodes (Stage F): optional generate_dialogue_audio after select
    from drama_forge.capabilities.audio import plan_dialogue_audio_nodes

    audio_nodes = plan_dialogue_audio_nodes(story, graph, assets=assets)
    for audio_node in audio_nodes:
        graph.add_edge(GraphEdge.create(audio_node.id, timeline_node.id))

    # Style-continuity edges: character refs already flow into scene/shot nodes.
    # Record an explicit style_continuity kind between scene ref and shot select
    # for traceability without introducing new scheduling constraints.
    for episode in story.episodes:
        for scene in episode.scenes:
            scene_node = scene_ref_nodes.get(scene.id)
            if scene_node is None:
                continue
            for shot in scene.shots:
                select_name = f"shot_select:{scene.index}.{shot.index}"
                select_node = next(
                    (n for n in graph.nodes.values() if n.name == select_name),
                    None,
                )
                if select_node is not None:
                    # kind is informational; dependencies already exist via generate chain
                    edge = GraphEdge.create(
                        scene_node.id, select_node.id, kind="style_continuity"
                    )
                    graph.add_edge(edge)

    graph.recompute_all_fingerprints()
    return GraphPlanResult(graph=graph, assets=assets)


def new_eval_id() -> str:
    """Temporary id placeholder replaced immediately after node creation."""
    return "pending"

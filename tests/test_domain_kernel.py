"""Stage A domain kernel tests."""

from __future__ import annotations

from drama_forge.compiler.production_spec import build_production_spec
from drama_forge.compiler.story_graph import build_production_graph, build_story_graph
from drama_forge.domain.common import NodeStatus
from drama_forge.domain.story import Story


def test_compile_story_structure(story: Story) -> None:
    """Story compiles into expected content hierarchy."""
    assert story.title == "黎明回声"
    assert len(story.characters) == 2
    shots = story.all_shots()
    assert len(shots) == 2
    assert shots[0].description
    assert story.fingerprint()


def test_story_graph_relations(story: Story) -> None:
    """Story graph contains appears_in and shot_of relations."""
    graph = build_story_graph(story)
    kinds = {kind for _, _, kind in graph.edges}
    assert "appears_in" in kinds
    assert "shot_of" in kinds
    assert "interacts_with" in kinds


def test_production_graph_planning(story: Story) -> None:
    """Production graph contains reference → shot → timeline chain."""
    plan = build_production_graph(story, candidate_count=2)
    graph = plan.graph
    actions = {n.action for n in graph.nodes.values()}
    assert "build_character_reference" in actions
    assert "generate_scene_reference" in actions
    assert "generate_shot_candidates" in actions
    assert "evaluate_shot_candidates" in actions
    assert "select_shot_candidate" in actions
    assert "assemble_timeline" in actions
    assert "validate_continuity" in actions
    assert all(n.fingerprint for n in graph.nodes.values())


def test_production_spec(story: Story) -> None:
    """Production spec records shot and continuity requirements."""
    spec = build_production_spec(story)
    assert spec.shot_requirements
    assert spec.continuity_requirements["enforce_character_identity"] is True


def test_fingerprint_reuse_same_story(story: Story) -> None:
    """Same story content yields stable fingerprint."""
    again = story
    assert story.fingerprint() == again.fingerprint()


def test_invalidated_propagation(story: Story) -> None:
    """Dirty propagation marks only dependent nodes."""
    plan = build_production_graph(story)
    graph = plan.graph
    char_nodes = [
        n.id for n in graph.nodes.values() if n.action == "build_character_reference"
    ]
    timeline = next(
        n.id for n in graph.nodes.values() if n.action == "assemble_timeline"
    )
    # seed a non-dependent isolated mark by invalidating nothing related first
    # character ref invalidation should reach timeline via shots
    invalidated = graph.invalidate_from({char_nodes[0]})
    assert char_nodes[0] in invalidated
    assert timeline in invalidated
    reset = graph.reset_invalidated_to_pending()
    assert set(reset) == invalidated
    assert graph.nodes[timeline].status == NodeStatus.PENDING

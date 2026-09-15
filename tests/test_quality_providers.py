"""Unit tests for quality runtime and providers."""

from __future__ import annotations

from drama_forge.domain.asset import Artifact, Candidate, CandidateSet
from drama_forge.domain.common import ArtifactType, GateResult, Severity
from drama_forge.domain.production import CanonicalGenerationSpec
from drama_forge.domain.quality import Issue
from drama_forge.providers.adapters import MockProvider
from drama_forge.providers.base import ProviderRequest
from drama_forge.providers.registry import ProviderRegistry
from drama_forge.providers.router import ProviderRouter
from drama_forge.quality.gates import gate_from_issues
from drama_forge.quality.validators import validate_artifact


def test_mock_provider_deterministic() -> None:
    """Same spec + candidate index yields same digest."""
    provider = MockProvider("p1")
    spec = CanonicalGenerationSpec(node_id="n1", capability="image_generation")
    r1 = provider.generate(ProviderRequest(capability="image_generation", generation_spec=spec))
    r2 = provider.generate(ProviderRequest(capability="image_generation", generation_spec=spec))
    assert r1.ok and r2.ok
    assert r1.generation_metadata["digest"] == r2.generation_metadata["digest"]


def test_router_decision_record() -> None:
    """Router records provider selection decision."""
    registry = ProviderRegistry()
    registry.register(MockProvider("a", quality_score=0.9, cost_score=0.2))
    registry.register(MockProvider("b", quality_score=0.5, cost_score=0.95))
    router = ProviderRouter(registry)
    provider, decision = router.select(
        "image_generation", {"strategy": "quality_first"}, subject="test"
    )
    assert provider.id == "a"
    assert decision.selected == "a"
    assert decision.candidates


def test_validate_artifact_blocks_missing_content() -> None:
    """Missing content_reference produces BLOCK."""
    artifact = Artifact.create(artifact_type=ArtifactType.IMAGE, content_reference="")
    artifact.technical_metadata = {"ok": True}
    result = validate_artifact(artifact)
    assert result.gate == GateResult.BLOCK


def test_candidate_ranking() -> None:
    """Candidates sort by weighted total score."""
    a = Artifact.create(artifact_type=ArtifactType.VIDEO, content_reference="x")
    b = Artifact.create(artifact_type=ArtifactType.VIDEO, content_reference="y")
    c1 = Candidate.create("n1", a)
    c2 = Candidate.create("n1", b)
    c1.quality_score = 0.9
    c2.quality_score = 0.3
    cs = CandidateSet(node_id="n1")
    cs.add(c1)
    cs.add(c2)
    assert cs.best() is c1
    selected = cs.select()
    assert selected is c1
    assert c1.selected and not c2.selected


def test_gate_from_issues() -> None:
    """High severity issues produce BLOCK."""
    issues = [Issue.create("VISUAL_QUALITY", Severity.HIGH, "bad")]  # type: ignore[arg-type]
    # fix with proper enum
    from drama_forge.domain.common import IssueType

    issues = [Issue.create(IssueType.VISUAL_QUALITY, Severity.HIGH, "bad")]
    assert gate_from_issues(issues) == GateResult.BLOCK
    low = [Issue.create(IssueType.VISUAL_QUALITY, Severity.LOW, "minor")]
    assert gate_from_issues(low) == GateResult.WARN

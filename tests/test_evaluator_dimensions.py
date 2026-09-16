"""W3a: Evaluator dimension four-state status and overall aggregation."""

from __future__ import annotations

from drama_forge.domain.asset import Artifact, Candidate, CandidateSet
from drama_forge.domain.common import (
    ArtifactType,
    DimensionStatus,
    GateResult,
)
from drama_forge.domain.quality import (
    DimensionMeasurement,
    QualityResult,
    compute_overall_score,
)
from drama_forge.quality.evaluators import (
    EVALUATION_DIMENSION_NAMES,
    evaluate_candidates,
)


def _make_candidate(
    node_id: str,
    digest: str,
    content_ref: str = "blob",
) -> Candidate:
    artifact = Artifact.create(
        artifact_type=ArtifactType.VIDEO,
        content_reference=content_ref,
        source_node=node_id,
    )
    artifact.generation_metadata["digest"] = digest
    return Candidate.create(node_id, artifact)


def _candidate_set(*digests: str, node_id: str = "node_eval") -> CandidateSet:
    cs = CandidateSet(node_id=node_id)
    for d in digests:
        cs.add(_make_candidate(node_id, d))
    return cs


def test_dimension_status_enum_values() -> None:
    """DimensionStatus exposes the four frozen string values."""
    assert set(DimensionStatus) == {
        DimensionStatus.MEASURED,
        DimensionStatus.PROXY,
        DimensionStatus.UNAVAILABLE,
        DimensionStatus.ERROR,
    }
    assert DimensionStatus.MEASURED == "measured"
    assert DimensionStatus.PROXY == "proxy"
    assert DimensionStatus.UNAVAILABLE == "unavailable"
    assert DimensionStatus.ERROR == "error"


def test_quality_result_defaults_are_legacy_compatible() -> None:
    """Omitting dimensions/overall keeps old constructor/call-site behavior."""
    qr = QualityResult.create(subject_id="n1", gate=GateResult.PASS)
    assert qr.dimensions == {}
    assert qr.overall is None
    assert qr.scores == {}
    # create() still accepts legacy kwargs only
    legacy = QualityResult.create(
        subject_id="n1",
        gate=GateResult.WARN,
        scores={"average_quality": 0.5},
    )
    assert legacy.scores["average_quality"] == 0.5
    assert legacy.dimensions == {}
    assert legacy.overall is None


def test_overall_mean_skips_unavailable_and_error() -> None:
    """unavailable/error never enter the mean and are not coerced to 0."""
    dims = {
        "a": DimensionMeasurement("a", score=0.8, status=DimensionStatus.MEASURED),
        "b": DimensionMeasurement("b", score=0.4, status=DimensionStatus.PROXY),
        "c": DimensionMeasurement("c", score=None, status=DimensionStatus.UNAVAILABLE),
        "d": DimensionMeasurement("d", score=None, status=DimensionStatus.ERROR),
    }
    overall = compute_overall_score(dims)
    assert overall is not None
    # mean of 0.8 and 0.4 only — not (0.8+0.4+0+0)/4
    assert abs(overall - 0.6) < 1e-9


def test_overall_none_when_all_unavailable() -> None:
    """All unavailable / empty dimensions → overall is None (not 0)."""
    empty = compute_overall_score({})
    assert empty is None
    all_unavailable = {
        "a": DimensionMeasurement("a", score=None, status=DimensionStatus.UNAVAILABLE),
        "b": DimensionMeasurement("b", score=None, status=DimensionStatus.ERROR),
    }
    assert compute_overall_score(all_unavailable) is None
    # even if someone stuffed a 0.0 score under unavailable, it must not count
    stuffed = {
        "a": DimensionMeasurement("a", score=0.0, status=DimensionStatus.UNAVAILABLE),
    }
    assert compute_overall_score(stuffed) is None


def test_measured_with_score_counts_toward_overall() -> None:
    """measured/proxy with non-None score contribute; proxy is not 0."""
    dims = {
        "q": DimensionMeasurement("q", score=1.0, status=DimensionStatus.MEASURED),
        "c": DimensionMeasurement("c", score=0.5, status=DimensionStatus.PROXY),
    }
    overall = compute_overall_score(dims)
    assert overall is not None
    assert abs(overall - 0.75) < 1e-9


def test_digest_heuristic_yields_proxy_and_heuristic_source() -> None:
    """No evaluation payload → digest fallback marks dimensions as proxy."""
    cs = _candidate_set("ab12cd34", "ff00ee11")
    result = evaluate_candidates(cs, None)
    assert result.dimensions, "expected dimensions from heuristic path"
    for name in EVALUATION_DIMENSION_NAMES:
        dim = result.dimensions[name]
        assert dim.status == DimensionStatus.PROXY
        assert dim.judge_source == "heuristic"
        assert dim.score is not None
    assert result.evidence["provenance"]["judge_source"] == "heuristic"
    assert result.evidence["provenance"]["dimension_status"] == "proxy"
    # overall still computed from proxy scores
    assert result.overall is not None
    assert 0.0 < result.overall <= 1.0
    # gate/scores stay compatible
    assert result.gate in (GateResult.PASS, GateResult.WARN)
    assert "average_quality" in result.scores
    assert result.scores["count"] == 2.0


def test_provider_payload_yields_measured_status() -> None:
    """Full provider score payload → measured + judge_source=provider."""
    cs = _candidate_set("aa", "bb")
    payload = {
        "scores": [
            {
                "candidate_index": 0,
                "quality_score": 0.9,
                "constraint_score": 0.8,
                "continuity_score": 0.7,
                "technical_score": 0.6,
            },
            {
                "candidate_index": 1,
                "quality_score": 0.5,
                "constraint_score": 0.5,
                "continuity_score": 0.5,
                "technical_score": 0.5,
            },
        ]
    }
    result = evaluate_candidates(cs, payload)
    assert set(result.dimensions) == set(EVALUATION_DIMENSION_NAMES)
    for dim in result.dimensions.values():
        assert dim.status == DimensionStatus.MEASURED
        assert dim.judge_source == "provider"
    assert result.evidence["provenance"]["judge_source"] == "provider"
    expected_quality_mean = (0.9 + 0.5) / 2
    assert abs(result.dimensions["quality_score"].score - expected_quality_mean) < 1e-9
    assert result.overall is not None
    # overall is mean of the four dimension means, not average_quality bag
    dim_mean = sum(d.score for d in result.dimensions.values()) / 4
    assert abs(result.overall - dim_mean) < 1e-9


def test_partial_payload_marks_set_as_proxy() -> None:
    """Mixed provider + heuristic candidates → set-level proxy (no over-claim)."""
    cs = _candidate_set("aa", "bb", "cc")
    payload = {
        "scores": [
            {
                "candidate_index": 0,
                "quality_score": 1.0,
                "constraint_score": 1.0,
                "continuity_score": 1.0,
                "technical_score": 1.0,
            }
        ]
    }
    result = evaluate_candidates(cs, payload)
    for dim in result.dimensions.values():
        assert dim.status == DimensionStatus.PROXY
        assert dim.judge_source == "heuristic+provider"


def test_recompute_overall_on_quality_result() -> None:
    """QualityResult.recompute_overall mirrors compute_overall_score."""
    dims = {
        "a": DimensionMeasurement("a", score=0.2, status=DimensionStatus.MEASURED),
        "b": DimensionMeasurement("b", score=None, status=DimensionStatus.UNAVAILABLE),
    }
    qr = QualityResult.create(
        subject_id="n",
        gate=GateResult.PASS,
        dimensions=dims,
    )
    assert qr.overall is None  # not auto-set at create
    recomputed = qr.recompute_overall()
    assert recomputed is not None
    assert abs(recomputed - 0.2) < 1e-9
    assert qr.overall == recomputed


def test_empty_candidate_set_overall_none_and_gate_warn() -> None:
    """Empty set: no dimensions, overall None, gate WARN (legacy)."""
    cs = CandidateSet(node_id="empty")
    result = evaluate_candidates(cs, None)
    assert result.dimensions == {}
    assert result.overall is None
    assert result.gate == GateResult.WARN
    assert result.scores["count"] == 0.0

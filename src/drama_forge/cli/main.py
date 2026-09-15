"""CLI entry: compile / plan / run / status / inspect / validate / repair."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from drama_forge.engine import Engine


def _print(data: Any) -> None:
    """Print JSON to stdout."""
    print(json.dumps(data, indent=2, ensure_ascii=False, default=str))


def build_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="drama-forge",
        description="Drama Forge Core Engine CLI",
    )
    parser.add_argument(
        "--artifact-root",
        default=None,
        help="Artifact store root directory",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_compile = sub.add_parser("compile", help="Compile story JSON to story summary")
    p_compile.add_argument("story", type=Path)

    p_plan = sub.add_parser("plan", help="Plan production graph from story")
    p_plan.add_argument("story", type=Path)
    p_plan.add_argument("--candidates", type=int, default=2)

    p_run = sub.add_parser("run", help="Run end-to-end production")
    p_run.add_argument("story", type=Path)
    p_run.add_argument("--candidates", type=int, default=2)
    p_run.add_argument(
        "--inject-continuity-issue",
        action="store_true",
        help="Force a continuity failure for repair demos",
    )

    p_status = sub.add_parser("status", help="Show execution status")
    p_status.add_argument("execution_id")

    p_inspect = sub.add_parser("inspect", help="Inspect artifact provenance")
    p_inspect.add_argument("artifact_id")

    p_validate = sub.add_parser("validate", help="Show quality report")
    p_validate.add_argument("execution_id")

    p_repair = sub.add_parser("repair", help="Plan and apply local repair")
    p_repair.add_argument("execution_id")
    p_repair.add_argument("story", type=Path)

    sub.add_parser("doctor", help="Self-check environment")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI main entry.

    Args:
        argv: Optional argument list (defaults to sys.argv[1:]).

    Returns:
        Process exit code.
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    engine = Engine(artifact_root=args.artifact_root)

    if args.command == "doctor":
        _print(
            {
                "ok": True,
                "providers": [p.id for p in engine.registry.all()],
                "artifact_root": str(engine.artifact_store.root),
            }
        )
        return 0

    if args.command == "compile":
        story = engine.compile(args.story)
        _print(
            {
                "id": story.id,
                "title": story.title,
                "characters": [c.name for c in story.characters.values()],
                "shot_count": len(story.all_shots()),
                "fingerprint": story.fingerprint(),
            }
        )
        return 0

    if args.command == "plan":
        story = engine.compile(args.story)
        manifest, plan, story_graph = engine.plan(
            story, candidate_count=args.candidates
        )
        _print(
            {
                "manifest_id": manifest.id,
                "graph_id": plan.graph.id,
                "node_count": len(plan.graph.nodes),
                "edge_count": len(plan.graph.edges),
                "asset_count": len(plan.assets),
                "story_graph_nodes": len(story_graph.nodes),
                "actions": sorted({n.action for n in plan.graph.nodes.values()}),
            }
        )
        return 0

    if args.command == "run":
        story = engine.compile(args.story)
        result = engine.run(
            story,
            candidate_count=args.candidates,
            inject_continuity_issue=args.inject_continuity_issue,
        )
        _print(
            {
                "execution_id": result.execution_id,
                "status": result.status.value,
                "gate": result.report.overall_gate.value,
                "timeline_artifact_id": (
                    result.timeline_artifact.id if result.timeline_artifact else None
                ),
                "selected": [
                    {
                        "id": c.id,
                        "node": c.node_id,
                        "score": c.total_score,
                        "artifact_id": c.artifact.id,
                    }
                    for c in result.selected_candidates()
                ],
                "issues": [
                    {
                        "type": i.issue_type.value,
                        "severity": i.severity.value,
                        "message": i.message,
                    }
                    for i in result.report.issues
                ],
            }
        )
        return 0

    if args.command == "status":
        status = engine.status(args.execution_id)
        if status is None:
            print(f"unknown execution: {args.execution_id}", file=sys.stderr)
            return 1
        _print(status)
        return 0

    if args.command == "inspect":
        trace = engine.inspect(args.artifact_id)
        if trace is None:
            print(f"unknown artifact: {args.artifact_id}", file=sys.stderr)
            return 1
        _print(trace)
        return 0

    if args.command == "validate":
        report = engine.validate(args.execution_id)
        if report is None:
            print(f"unknown execution: {args.execution_id}", file=sys.stderr)
            return 1
        _print(
            {
                "gate": report.overall_gate.value,
                "results": [
                    {
                        "subject": r.subject_id,
                        "gate": r.gate.value,
                        "issues": len(r.issues),
                    }
                    for r in report.results
                ],
            }
        )
        return 0

    if args.command == "repair":
        story = engine.compile(args.story)
        plan, new_result = engine.repair(args.execution_id, story=story)
        _print(
            {
                "repair_plan_id": plan.id,
                "kind": plan.kind.value,
                "invalidate_nodes": plan.invalidate_node_ids,
                "keep_nodes": plan.keep_node_ids,
                "new_execution_id": new_result.execution_id,
                "new_status": new_result.status.value,
            }
        )
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

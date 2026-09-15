# Drama Forge

Core Engine for productized AI drama production.

## What this is

Drama Forge turns story content into a repeatable, recoverable, repairable production graph:

```
Story → Compiler → Production Spec / Manifest → Production Graph
  → Execution Runtime → Capability / Provider
  → Artifact / Candidate → Quality Gate → Select / Repair
  → Canonical Timeline → Provenance
```

It is **not** a Studio UI, SaaS layer, or prompt library. See design docs in
`docs-nocommit/` (local-only).

## Requirements

- Python 3.11+

## Install

```bash
pip install -e ".[dev]"
```

## Programmatic API

```python
from drama_forge import Engine

engine = Engine()
story = engine.compile("examples/story_sample.json")
result = engine.run(story, candidate_count=2)
print(result.status, result.timeline_artifact.id)
print(engine.inspect(result.timeline_artifact.id))
```

## CLI

```bash
python -m drama_forge.cli.main doctor
python -m drama_forge.cli.main compile examples/story_sample.json
python -m drama_forge.cli.main plan examples/story_sample.json
python -m drama_forge.cli.main run examples/story_sample.json
python -m drama_forge.cli.main run examples/story_sample.json --inject-continuity-issue
python -m drama_forge.cli.main status <execution-id>
python -m drama_forge.cli.main inspect <artifact-id>
python -m drama_forge.cli.main validate <execution-id>
python -m drama_forge.cli.main repair <execution-id> examples/story_sample.json
```

## Tests

```bash
python -m pytest -v
```

Covers domain kernel, execution runtime, provider routing, quality/repair, and
the nine core engineering validations.

## Package layout

```
src/drama_forge/
  domain/       # story, asset, production, quality
  compiler/     # parser, story graph, production spec
  runtime/      # scheduler, worker, checkpoint, events
  providers/    # registry, router, mock adapters
  artifacts/    # typed artifact store + provenance
  quality/      # validators, evaluators, gates, repair
  engine.py     # programmatic facade
  cli/          # verification CLI
```

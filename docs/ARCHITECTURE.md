[![English](https://img.shields.io/badge/English-Architecture-blue)](ARCHITECTURE.md)
[![简体中文](https://img.shields.io/badge/简体中文-架构-green)](ARCHITECTURE.zh-CN.md)

# Architecture

This page is the **public architecture overview**. It describes the stable cores and data flow of Drama Forge Core Engine. It is not the full implementation plan and does not list every module.

## Positioning

Drama Forge turns story content into a **repeatable, recoverable, repairable** production graph.

It does **not** ship:

- Studio / Canvas / visual authoring workbench
- SaaS business layer (users, billing, orgs, collaboration)
- Agent as the production Runtime
- Prompt as the core asset
- A Provider-specific workflow as the production model

## Production loop

```
Story Source
  → Story Compiler → Story Model / Story Graph
  → Production Spec / Manifest
  → Canonical Production Model
  → Production Graph
  → Execution Runtime
  → Capability Router → Provider
  → Artifact / Candidate
  → Quality Runtime (Validate / Evaluate / Gate / Issue / Repair)
  → Select / Partial Repair / Dirty Propagation
  → Canonical Timeline
  → Production Knowledge
```

Success is **not** “can generate one video”. Success is whether the process can be repeated, recovered, repaired locally, traced, and evolved.

## Five stable cores

```text
┌──────────────────────────────────────────────────────────────┐
│                     Programmatic facade                      │
│                    engine.py  /  CLI                         │
└───────────┬──────────────────────────────┬───────────────────┘
            │                              │
            ▼                              ▼
┌─────────────────────┐        ┌─────────────────────┐
│   Domain Model      │        │  Production Model   │
│  Story/Asset/Shot   │───────▶│  Spec/Graph/Policy  │
└─────────┬───────────┘        └─────────┬───────────┘
          │                              │
          └──────────────┬───────────────┘
                         ▼
            ┌────────────────────────┐
            │  Execution Runtime     │
            │  Scheduler/Checkpoint  │
            └───────────┬────────────┘
                        ▼
            ┌────────────────────────┐
            │  Artifact Runtime      │
            │  Store/Provenance      │
            └───────────┬────────────┘
                        ▼
            ┌────────────────────────┐
            │  Quality Runtime       │
            │  Gate/Issue/Repair     │
            └────────────────────────┘
```

| Core | Responsibility |
|------|----------------|
| **Domain Model** | Story, World, Character, Scene, Shot, Asset, Relationship, Timeline objects |
| **Production Model** | Manifest / Spec / Production Graph (Node + Edge + Fingerprint + Policy) |
| **Execution Runtime** | ExecutionPlan, Scheduler, Task, Worker, Checkpoint, Retry, Events, Cancel |
| **Artifact Runtime** | Typed Artifact, ArtifactStore, Provenance, Fingerprint cache |
| **Quality Runtime** | Validator, Evaluator, Gate, Issue, RepairPlanner |

## Decoupling principles

> Production definition is decoupled from Provider.  
> Production graph is decoupled from executor.  
> Semantic asset is decoupled from concrete files.  
> Quality judgment is decoupled from repair action.

### Canonical intermediate layer

Provider output must be absorbed into Drama Forge’s own Canonical Production Model. Third-party API response shapes must never become the core production model.

## Concept pairs

| Concept A | Concept B | Difference |
|-----------|-----------|------------|
| Asset | Artifact | Semantic identity vs a concrete generation result |
| Retry | Repair | Re-run same failed Task vs re-produce after definition/result quality failure |
| Event | Decision Record | What happened vs why this decision |
| Fingerprint | Provenance | Same production conditions vs how a result was produced |
| Provenance | Production Knowledge | Historical record vs stable rules that can enter the next Spec |

## Capability and Provider

- Capabilities are declared on the production graph (`text_generation`, `image_generation`, …).
- Providers register against capabilities; Mock providers work offline by default.
- Routing can be pinned per capability via `provider_policy["by_capability"]` **without changing the production graph**.
- Real providers (OpenAI-compatible HTTP, DeepSeek, SiliconFlow, Agnes, …) plug in behind the same capability surface and support dry-run fallbacks.

## Persistence

Optional SQLite history (`db_path`) stores production objects, candidates, execution events, quality results, and production knowledge (schema v2). Artifacts live in a local artifact store; the database stores metadata and provenance, not binary blobs as source of truth.

## Entry surfaces

```python
from drama_forge import Engine

engine = Engine(db_path="production.db")
story = engine.compile("examples/story_sample.json")
result = engine.run(story, candidate_count=2)
print(engine.inspect(result.timeline_artifact.id))
```

```bash
drama-forge compile|plan|run|status|inspect|validate|repair|doctor|version
```

## Related docs

- [Contributing](CONTRIBUTING.md)
- [Roadmap](ROADMAP.md)
- [Packaging](PACKAGING.md)
- [Architecture Decision Records](ADR.md)
- [LLM / Provider guides](LLM_PROVIDERS.md)

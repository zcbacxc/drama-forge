[![English](https://img.shields.io/badge/English-ADR-blue)](ADR.md)
[![简体中文](https://img.shields.io/badge/简体中文-架构决策记录-green)](ADR.zh-CN.md)

# Architecture Decision Records

This file records significant architecture decisions for **Drama Forge**. Each ADR is short, self-contained, and immutable once accepted — if a decision changes, write a new ADR that supersedes the old one.

## Decision index

| ID | Title | Status |
|----|-------|--------|
| [ADR-001](#adr-001-canonical-intermediate-layer) | Canonical intermediate layer | Accepted |
| [ADR-002](#adr-002-provider-decoupling-and-capability-routing) | Provider decoupling and capability routing | Accepted |
| [ADR-003](#adr-003-mock-first-and-dry-run-fallback) | Mock-first and dry-run fallback | Accepted |
| [ADR-004](#adr-004-persistence-sqlite-and-local-artifact-store) | Persistence: SQLite + local artifact store | Accepted |
| [ADR-005](#adr-005-programmatic-facade-and-cli-as-primary-entries) | Programmatic facade and CLI as primary entries | Accepted |
| [ADR-006](#adr-006-agpl-3.0-or-later-licensing) | AGPL-3.0-or-later licensing | Accepted |

---

## ADR-001: Canonical intermediate layer

**Status:** Accepted

### Context

LLM / image / video providers each return their own JSON shapes. If those shapes leak into the core model, every adapter change becomes a domain change.

### Decision

Absorb all provider outputs into Drama Forge’s **Canonical Production Model** (Story / Asset / Spec / Graph / Artifact / Candidate). Provider-specific payloads stay behind adapters.

### Consequences

- Domain and Quality layers remain stable when swapping providers
- Adapters own normalization cost
- Some provider-specific fields may be dropped unless mapped into Canonical fields or Provenance metadata

---

## ADR-002: Provider decoupling and capability routing

**Status:** Accepted

### Context

Tight coupling of production graphs to a single vendor blocks replacement, testing, and cost routing.

### Decision

- Production graphs declare **capabilities** (`text_generation`, `image_generation`, …), not vendor APIs
- Providers register against capabilities
- Optional `provider_policy["by_capability"]` pins providers **without rewriting the production graph**

### Consequences

- Same graph can run on Mock, OpenAI-compatible HTTP, DeepSeek, SiliconFlow, Agnes, etc.
- Routing policy is configuration, not a fork of the Spec
- Capability names become a contract surface and need care when renaming

---

## ADR-003: Mock-first and dry-run fallback

**Status:** Accepted

### Context

CI and first-run experience must not require paid API keys. Live calls are optional verification, not the default path.

### Decision

- Default provider family is **mock** (deterministic, offline)
- HTTP adapters support **dry-run** deterministic fallbacks when keys are missing or `DRAMA_FORGE_PROVIDER_DRY_RUN` is set
- Live smoke tests are opt-in (`DRAMA_FORGE_LIVE_SMOKE=1`)

### Consequences

- Nine core validations and unit tests run offline
- Mock fidelity must stay good enough that graph/runtime/quality logic is still exercised
- Live behavior differences are confined to adapter tests

---

## ADR-004: Persistence: SQLite + local artifact store

**Status:** Accepted

### Context

Core Engine needs recoverable history and provenance without forcing a distributed datastore.

### Decision

- Optional SQLite database (`db_path`) for production objects, candidates, events, quality results, knowledge
- Binaries live in a local artifact store; DB stores metadata, fingerprints, and provenance references
- Schema is versioned (currently v2) with migrations

### Consequences

- Zero-ops local recoverability and inspectability
- Not a multi-tenant SaaS store; that remains out of scope
- Future remote stores can replace the repository layer without changing Domain

---

## ADR-005: Programmatic facade and CLI as primary entries

**Status:** Accepted

### Context

A productized engine needs a stable embeddable API and a verification CLI. An HTTP service is a different product boundary.

### Decision

Primary entries are:

- `drama_forge.Engine` (Python facade)
- `drama-forge` console script / `python -m drama_forge.cli.main`

No first-class HTTP API in Core Engine scope.

### Consequences

- Embedders and tests share the same path
- Studio / SaaS layers (if any) live outside this repository
- CLI remains a verification surface, not a full product UI

---

## ADR-006: AGPL-3.0-or-later licensing

**Status:** Accepted

### Context

Network-copyleft protects the engine if someone offers it as a hosted service, while remaining OSI-approved.

### Decision

- License: **AGPL-3.0-or-later** (SPDX; not deprecated `AGPL-3.0`)
- `pyproject.toml` uses PEP 639 string form; no license trove classifier
- Source files under `src/drama_forge/` carry SPDX headers

### Consequences

- Downstream commercial closed forks need compliance review
- Third-party generated media licensing remains the end user’s responsibility

---

## Template for new ADRs

```markdown
## ADR-NNN: Short title

**Status:** Proposed | Accepted | Superseded by ADR-MMM

### Context
What forces the decision?

### Decision
What did we choose?

### Consequences
What becomes easier / harder?
```

1. Pick the next number
2. Add the section below
3. Append a row to the Decision Index
4. Keep the record grounded in this codebase — do not invent architecture that does not exist

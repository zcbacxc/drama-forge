[![English](https://img.shields.io/badge/English-Roadmap-blue)](ROADMAP.md)
[![简体中文](https://img.shields.io/badge/简体中文-路线图-green)](ROADMAP.zh-CN.md)

# Roadmap

> Per-release details live in [CHANGELOG.md](../CHANGELOG.md). This page summarizes shipped themes and the near-term direction only.

## Planning principles

1. Serve **Core Engine** positioning only — no Studio, SaaS, or Agent-as-Runtime scope.
2. Prefer engineering properties (repeat / recover / repair / trace / swap Provider) over one-off demos.
3. Alternate user-visible capabilities with infrastructure hardening.
4. Do not claim “production-ready Core Engine” until the nine core engineering validations are all green.

## Shipped

| Version | Theme |
|---------|-------|
| 0.1.0 | Domain kernel, compiler, execution runtime, capability routing, mock + HTTP providers, artifact/provenance, quality/repair, Stage F capabilities, timeline, SQLite persistence, CLI, core validation tests, CI + publish workflow |

## Near-term (planned)

Themes are ordered for engineering risk reduction, not marketing milestones.

### Public docs & packaging

- Bilingual `docs/` set (this batch)
- First PyPI Trusted Publishing release once ready
- Optional mkdocs site when API reference volume justifies it

### Runtime depth

- Stronger dirty-propagation and partial re-production paths
- Richer failure-class semantics in operational tooling
- Production Knowledge feedback into continuity constraints (hardened)

### Capability / Provider

- Additional OpenAI-compatible endpoints behind the same adapter
- Image / video capability contract hardening and live smoke expansion
- Cost and usage accounting surfaced in execution metadata

### Quality

- More validators/evaluators for continuity and candidate ranking
- Repair plans that map issues to minimal graph invalidation

## Explicitly out of scope

| Not in Drama Forge Core | Rationale |
|-------------------------|-----------|
| Studio / Canvas UI | Separate product layer |
| SaaS accounts, billing, orgs | Separate product layer |
| Agent as sole production Runtime | Must not bypass Graph / Contract / Checkpoint / Provenance |
| Prompt-as-core-asset store | Prompts are inputs, not the production model |
| Plugin marketplace | Capability extensions stay in-code or explicit adapters |

## How to influence the roadmap

- Open a [feature request](https://github.com/zcbacxc/drama-forge/issues/new?template=feature_request.md) and state how it serves the production loop
- For implementation discussion, use [Discussions](https://github.com/zcbacxc/drama-forge/discussions)
- See also [ARCHITECTURE.md](ARCHITECTURE.md) for current stable cores

[![English](https://img.shields.io/badge/English-AI_Guide-blue)](AI_GUIDE.md)
[![简体中文](https://img.shields.io/badge/简体中文-AI指南-green)](AI_GUIDE.zh-CN.md)

# AI Coding Assistant Guide

> Navigation index for AI coding tools (Claude Code, Codex, Cursor, Copilot, etc.). Content lives in the linked documents; this page only routes.

## Start here

| Topic | Document |
|-------|----------|
| Overview and install | [README](../README.md) |
| Chinese README | [README.zh-CN](../README.zh-CN.md) |
| Architecture (five cores, loop) | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Contributing rules | [CONTRIBUTING.md](CONTRIBUTING.md) |

## Design decisions

| Topic | Document |
|-------|----------|
| ADR index and template | [ADR.md](ADR.md) |
| Provider guides | [LLM_PROVIDERS.md](LLM_PROVIDERS.md) |
| Versioning and PyPI | [PACKAGING.md](PACKAGING.md) |
| Shipped / planned themes | [ROADMAP.md](ROADMAP.md) |

## Invariants for edits

1. Core Engine only — no Studio / SaaS / Agent-as-Runtime scope creep
2. Provider details must not become Domain / Canonical model
3. No internal tracking codes (EP*, WP*, NA-M*, …) in public docs or commits
4. Public bilingual docs stay structure-aligned (`.md` + `.zh-CN.md`)
5. Local design docs (`PROJECT_POSITIONING.md`, `docs-nocommit/`) must **not** be committed or copied into `docs/`
6. Update CHANGELOG for user-facing changes; keep version in `pyproject.toml` as source of truth

## CLI cheat sheet

```bash
drama-forge version
drama-forge doctor
drama-forge compile examples/story_sample.json
drama-forge run examples/story_sample.json
drama-forge status <execution-id>
drama-forge inspect <artifact-id>
drama-forge validate <execution-id>
drama-forge repair <execution-id> examples/story_sample.json
```

## Local-only (do not publish)

| File | Role |
|------|------|
| `PROJECT_POSITIONING.md` | Positioning / non-goals (gitignored) |
| `docs-nocommit/confirmed/IMPLEMENTATION_PLAN.md` | Full engineering plan (gitignored) |
| `.claude/rules/` | Path-scoped agent rules (gitignored) |

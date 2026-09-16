# Changelog

All notable changes to Drama Forge Core Engine are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Public bilingual `docs/` set: architecture, contributing, roadmap, packaging, ADR, LLM/provider guides, AI guide index
- GitHub PR template and issue templates (bug / feature / config)
- CostTracker wiring (W4a): `ExecutionContext.cost_tracker` injected by `Engine.run` / `Engine._run_graph`; `ProductionWorker` records every `provider.generate` outcome (best-effort, never fails the task); `RunResult.cost_summary()` exposes the execution rollup
- Provider outcome events `provider.called` / `provider.failed` carry cost, latency, and usage

### Fixed
- `CostTracker` is now thread-safe under `Scheduler(max_workers>1)` (`record` / summary reads guarded by a lock)
- `MockProvider` / `MockEvaluatorProvider` call counters are thread-safe so parallel tests can use them as ground truth

## [0.1.0] - 2026-09-15

Initial public release of the Core Engine implementation plan (stages A–F).

### Added
- Domain kernel: Story / Character / Scene / Shot / Asset / Artifact / Candidate / Production Graph / Fingerprint
- Story compiler: parser, story graph, production spec, production graph planner
- Execution runtime: scheduler, worker, retry, checkpoint, events, fingerprint reuse, cooperative cancel
- Capability routing: registry, strategy router (including `reliability_first`), decision records
- Providers: local mock set, OpenAI-compatible HTTP adapter (dry-run safe), env-driven factory, CostTracker
- Typed artifact store with provenance and fingerprint cache
- Quality runtime: validators, evaluators, gates, repair planner, dirty propagation
- Stage F capabilities: capability registry, character/scene consistency, dialogue audio planning
- Timeline package: canonical timeline model and renderer with audio alignment and segment substitution
- Domain continuity models (rules, findings, report)
- SQLite persistence layer (11 tables, migrations, 8 repositories) wired into Engine via `db_path`
- Programmatic `Engine` facade and verification CLI (`compile` / `plan` / `run` / `status` / `inspect` / `validate` / `repair` / `doctor` / `version`)
- Nine core engineering validations covered by tests
- GitHub Actions CI (lint, tests, CLI smoke) and tag release gate
- Production Knowledge domain: harvest from story + execution, merge/version, inject into continuity constraints, SQLite persistence
- Parallel graph scheduler (`Scheduler(max_workers=...)`) with cooperative `CancellationToken`
- Typed `FailureClass` semantics (HARD/SOFT/PARTIAL/BLOCKED/SKIPPED/DEGRADED) on task results
- External Production Manifest JSON contract (`load_manifest_file` / `dump_manifest_file`)
- Persistence schema v2: `production_knowledge`, `candidates`, `execution_events` tables and repositories
- DeepSeek as an OpenAI-compatible HTTP preset (`chat/completions` path, `deepseek-flash` default model)
- SiliconFlow image provider adapter (`siliconflow-image`) for `/v1/images/generations`
- Agnes image via shared images adapter (`agnes-image`, default `agnes-image-2.0-flash`)
- Agnes video provider adapter (`agnes-video`) for gateway `POST /v1/videos`
- Factory families: `deepseek`, `siliconflow`/`sf`, `agnes`/`agnes-video`, `agnes-image`, `production` (= `deepseek+siliconflow`), and `a+b` combinations
- Per-capability provider routing via `provider_policy["by_capability"]`
- Configurable `HttpProviderConfig.chat_path` and `reasoning_content` fallback in the shared adapter
- Offline contract tests and optional live smoke (`DRAMA_FORGE_LIVE_SMOKE=1`)
- PyPI packaging and OIDC Trusted Publishing workflow (`publish.yml`)

### Fixed
- `.gitignore` root-scoped `artifacts/` so `src/drama_forge/artifacts/` is tracked
- OpenAI-compatible chat endpoint joining when `base_url` already ends with `/v1`

[Unreleased]: https://github.com/zcbacxc/drama-forge/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/zcbacxc/drama-forge/releases/tag/v0.1.0

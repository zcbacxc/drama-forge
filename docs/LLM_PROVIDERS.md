[![English](https://img.shields.io/badge/English-LLM_Providers-blue)](LLM_PROVIDERS.md)
[![简体中文](https://img.shields.io/badge/简体中文-LLM_Providers-green)](LLM_PROVIDERS.zh-CN.md)

# LLM / Provider Guides

Drama Forge talks to providers through a **capability** surface, not vendor-specific production graphs. This directory documents how to configure each supported backend.

| Guide | Capability focus | Notes |
|-------|------------------|-------|
| [Mock (default)](#mock-default) | all | Offline, deterministic, zero config |
| [OpenAI-compatible](llm-providers/openai-compatible.md) | text | Generic HTTP chat completions |
| [DeepSeek](llm-providers/deepseek.md) | text | OpenAI-compatible preset (`chat/completions`) |
| [SiliconFlow](llm-providers/siliconflow.md) | image | `/v1/images/generations` |
| [Agnes](llm-providers/agnes.md) | image + video | Gateway image + `POST /v1/videos` |

## Mock (default)

```bash
# unset DRAMA_FORGE_PROVIDER, or:
export DRAMA_FORGE_PROVIDER=mock
```

No keys, no network. Suitable for tests, CI, and graph/runtime debugging.

## Selecting a family

```bash
export DRAMA_FORGE_PROVIDER=deepseek
export DRAMA_FORGE_DEEPSEEK_API_KEY=sk-...

# text + image production preset
export DRAMA_FORGE_PROVIDER=production
export DRAMA_FORGE_DEEPSEEK_API_KEY=sk-...
export DRAMA_FORGE_SILICONFLOW_API_KEY=sk-...

# combine families with a+b
export DRAMA_FORGE_PROVIDER=deepseek+siliconflow
```

### Offline safety

```bash
export DRAMA_FORGE_PROVIDER_DRY_RUN=1
```

HTTP adapters fall back to deterministic offline results when dry-run is on or credentials are missing.

### Per-capability pin (no graph change)

```python
policy = {
    "strategy": "balanced",
    "by_capability": {
        "text_generation": {"provider_id": "deepseek"},
        "image_generation": {"provider_id": "siliconflow-image"},
    },
}
result = engine.run(story, provider_policy=policy)
```

## Configuration locations

Priority (highest first):

1. Process environment (`DRAMA_FORGE_*`)
2. Project `.env`
3. User `~/.drama-forge/.env` (auto-created from `.env.example`)

Copy `.env.example` from the repository root as a template. Story content is **not** configured here — use story JSON / Manifest.

## Related

- [Architecture — Capability and Provider](ARCHITECTURE.md#capability-and-provider)
- [Contributing](CONTRIBUTING.md)

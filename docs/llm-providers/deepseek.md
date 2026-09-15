[![English](https://img.shields.io/badge/English-DeepSeek-blue)](deepseek.md)
[![简体中文](https://img.shields.io/badge/简体中文-DeepSeek-green)](deepseek.zh-CN.md)

# DeepSeek

DeepSeek is used through the shared **OpenAI-compatible** adapter (no vendor-specific production graph).

## Capability

- `text_generation`

## Environment

```bash
export DRAMA_FORGE_PROVIDER=deepseek
# or: export DRAMA_FORGE_PROVIDER=production   # deepseek + siliconflow

export DRAMA_FORGE_DEEPSEEK_API_KEY=sk-...
# optional overrides
# export DRAMA_FORGE_DEEPSEEK_BASE_URL=https://api.deepseek.com
# export DRAMA_FORGE_DEEPSEEK_MODEL=deepseek-flash
# export DRAMA_FORGE_DEEPSEEK_TIMEOUT=60
# export DRAMA_FORGE_DEEPSEEK_CHAT_PATH=chat/completions
# export DRAMA_FORGE_PROVIDER_DRY_RUN=1
```

## Notes (live-verified preset)

- Chat path is `chat/completions` (not `/v1/chat/completions`)
- Default model is `deepseek-flash` (`DRAMA_FORGE_DEEPSEEK_MODEL`)
- Empty `content` may fall back to `reasoning_content` in the shared adapter
- Missing key or dry-run yields deterministic offline fallbacks

## Pin without changing the graph

```python
policy = {"by_capability": {"text_generation": {"provider_id": "deepseek"}}}
result = engine.run(story, provider_policy=policy)
```

## See also

- [LLM Providers overview](../LLM_PROVIDERS.md)
- [OpenAI-compatible](openai-compatible.md)
- [Architecture](../ARCHITECTURE.md)

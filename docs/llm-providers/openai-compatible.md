[![English](https://img.shields.io/badge/English-OpenAI_Compatible-blue)](openai-compatible.md)
[![简体中文](https://img.shields.io/badge/简体中文-OpenAI_Compatible-green)](openai-compatible.zh-CN.md)

# OpenAI-compatible HTTP

Generic adapter for any OpenAI-style chat completions endpoint.

## Capability

- `text_generation`

## Environment

```bash
export DRAMA_FORGE_PROVIDER=openai_compatible

export DRAMA_FORGE_PROVIDER_BASE_URL=https://api.openai.com
export DRAMA_FORGE_PROVIDER_API_KEY=sk-...
export DRAMA_FORGE_PROVIDER_MODEL=gpt-4o-mini
# optional
# export DRAMA_FORGE_PROVIDER_TIMEOUT=30
# export DRAMA_FORGE_PROVIDER_ID=openai-compatible
# export DRAMA_FORGE_PROVIDER_CHAT_PATH=v1/chat/completions
# export DRAMA_FORGE_PROVIDER_DRY_RUN=1
```

## Notes

- If `base_url` already ends with `/v1`, path joining does not duplicate it
- `chat_path` is configurable for vendors that differ from the OpenAI layout
- Missing key or dry-run → deterministic offline fallback
- The adapter is also the basis for the DeepSeek preset

## See also

- [LLM Providers overview](../LLM_PROVIDERS.md)
- [DeepSeek](deepseek.md)

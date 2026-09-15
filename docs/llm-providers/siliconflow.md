[![English](https://img.shields.io/badge/English-SiliconFlow-blue)](siliconflow.md)
[![简体中文](https://img.shields.io/badge/简体中文-SiliconFlow-green)](siliconflow.zh-CN.md)

# SiliconFlow

SiliconFlow is used for **image generation** via the shared images adapter.

## Capability

- `image_generation`

## Environment

```bash
export DRAMA_FORGE_PROVIDER=siliconflow
# or: export DRAMA_FORGE_PROVIDER=production

export DRAMA_FORGE_SILICONFLOW_API_KEY=sk-...
# optional overrides
# export DRAMA_FORGE_SILICONFLOW_BASE_URL=https://api.siliconflow.cn
# export DRAMA_FORGE_SILICONFLOW_IMAGE_MODEL=Kwai-Kolors/Kolors
# export DRAMA_FORGE_SILICONFLOW_IMAGE_SIZE=1024x1024
# export DRAMA_FORGE_SILICONFLOW_ID=siliconflow-image
# export DRAMA_FORGE_PROVIDER_DRY_RUN=1
```

## Notes

- Endpoint: `/v1/images/generations`
- Prompts are built from the **canonical** image spec (not raw chat transcripts)
- Missing image URL in a successful response is treated as an error
- Dry-run / missing key → deterministic offline fallback artifacts

## Pin without changing the graph

```python
policy = {"by_capability": {"image_generation": {"provider_id": "siliconflow-image"}}}
result = engine.run(story, provider_policy=policy)
```

## See also

- [LLM Providers overview](../LLM_PROVIDERS.md)
- [DeepSeek](deepseek.md)
- [Architecture](../ARCHITECTURE.md)

[![English](https://img.shields.io/badge/English-Agnes-blue)](agnes.md)
[![简体中文](https://img.shields.io/badge/简体中文-Agnes-green)](agnes.zh-CN.md)

# Agnes (image + video)

Agnes is accessed through a gateway adapter for **image** and **video** generation.

## Capabilities

- `image_generation` → provider id `agnes-image`
- `video_generation` → provider id `agnes-video` (when enabled)

## Environment

```bash
export DRAMA_FORGE_PROVIDER=agnes-image
# or video-capable family: export DRAMA_FORGE_PROVIDER=agnes

export DRAMA_FORGE_AGNES_BASE_URL=https://your-gateway/v1
export DRAMA_FORGE_AGNES_API_KEY=...
# optional
# export DRAMA_FORGE_AGNES_IMAGE_MODEL=agnes-image-2.0-flash
# export DRAMA_FORGE_AGNES_IMAGE_ID=agnes-image
# export DRAMA_FORGE_AGNES_MODEL=agnes-video-2.5-flash
# export DRAMA_FORGE_AGNES_MODE=t2v
# export DRAMA_FORGE_AGNES_ID=agnes-video
# export DRAMA_FORGE_AGNES_TIMEOUT=120
# export DRAMA_FORGE_PROVIDER_DRY_RUN=1
```

## Notes

- Image responses follow the OpenAI `data[].url` shape (live-verified path)
- Video uses gateway `POST /v1/videos` with `mode=T2V` by default
- Models such as `agnes-video-2.5-flash` / `2.5` / `v2.0` are selected via `DRAMA_FORGE_AGNES_MODEL`
- Dry-run / missing credentials → offline deterministic fallbacks

## See also

- [LLM Providers overview](../LLM_PROVIDERS.md)
- [SiliconFlow](siliconflow.md)

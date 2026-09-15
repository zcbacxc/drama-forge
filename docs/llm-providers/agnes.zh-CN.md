[![English](https://img.shields.io/badge/English-Agnes-blue)](agnes.md)
[![简体中文](https://img.shields.io/badge/简体中文-Agnes-green)](agnes.zh-CN.md)

# Agnes（图像 + 视频）

Agnes 通过网关适配器接入**图像**与**视频**生成。

## 能力

- `image_generation` → provider id `agnes-image`
- `video_generation` → provider id `agnes-video`（启用时）

## 环境变量

```bash
export DRAMA_FORGE_PROVIDER=agnes-image
# 或含视频能力的 family：export DRAMA_FORGE_PROVIDER=agnes

export DRAMA_FORGE_AGNES_BASE_URL=https://your-gateway/v1
export DRAMA_FORGE_AGNES_API_KEY=...
# 可选
# export DRAMA_FORGE_AGNES_IMAGE_MODEL=agnes-image-2.0-flash
# export DRAMA_FORGE_AGNES_IMAGE_ID=agnes-image
# export DRAMA_FORGE_AGNES_MODEL=agnes-video-2.5-flash
# export DRAMA_FORGE_AGNES_MODE=t2v
# export DRAMA_FORGE_AGNES_ID=agnes-video
# export DRAMA_FORGE_AGNES_TIMEOUT=120
# export DRAMA_FORGE_PROVIDER_DRY_RUN=1
```

## 说明

- 图像响应遵循 OpenAI `data[].url` 形状（live 已验证路径）
- 视频走网关 `POST /v1/videos`，默认 `mode=T2V`
- 模型（如 `agnes-video-2.5-flash` / `2.5` / `v2.0`）由 `DRAMA_FORGE_AGNES_MODEL` 选择
- dry-run / 缺凭据 → 离线确定性回退

## 参见

- [LLM Providers 总览](../LLM_PROVIDERS.zh-CN.md)
- [SiliconFlow](siliconflow.zh-CN.md)

[![English](https://img.shields.io/badge/English-SiliconFlow-blue)](siliconflow.md)
[![简体中文](https://img.shields.io/badge/简体中文-SiliconFlow-green)](siliconflow.zh-CN.md)

# SiliconFlow

SiliconFlow 通过共享的图像适配器用于**图像生成**。

## 能力

- `image_generation`

## 环境变量

```bash
export DRAMA_FORGE_PROVIDER=siliconflow
# 或：export DRAMA_FORGE_PROVIDER=production

export DRAMA_FORGE_SILICONFLOW_API_KEY=sk-...
# 可选覆盖
# export DRAMA_FORGE_SILICONFLOW_BASE_URL=https://api.siliconflow.cn
# export DRAMA_FORGE_SILICONFLOW_IMAGE_MODEL=Kwai-Kolors/Kolors
# export DRAMA_FORGE_SILICONFLOW_IMAGE_SIZE=1024x1024
# export DRAMA_FORGE_SILICONFLOW_ID=siliconflow-image
# export DRAMA_FORGE_PROVIDER_DRY_RUN=1
```

## 说明

- 端点：`/v1/images/generations`
- Prompt 从**canonical** 图像规格构建（不是原始聊天转写）
- 成功响应中缺少 image URL 视为错误
- dry-run / 缺 Key → 确定性离线回退产物

## 不改生产图的钉选方式

```python
policy = {"by_capability": {"image_generation": {"provider_id": "siliconflow-image"}}}
result = engine.run(story, provider_policy=policy)
```

## 参见

- [LLM Providers 总览](../LLM_PROVIDERS.zh-CN.md)
- [DeepSeek](deepseek.zh-CN.md)
- [架构](../ARCHITECTURE.zh-CN.md)

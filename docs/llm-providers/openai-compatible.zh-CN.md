[![English](https://img.shields.io/badge/English-OpenAI_Compatible-blue)](openai-compatible.md)
[![简体中文](https://img.shields.io/badge/简体中文-OpenAI_Compatible-green)](openai-compatible.zh-CN.md)

# OpenAI-compatible HTTP

适用于任意 OpenAI 风格 chat completions 端点的通用适配器。

## 能力

- `text_generation`

## 环境变量

```bash
export DRAMA_FORGE_PROVIDER=openai_compatible

export DRAMA_FORGE_PROVIDER_BASE_URL=https://api.openai.com
export DRAMA_FORGE_PROVIDER_API_KEY=sk-...
export DRAMA_FORGE_PROVIDER_MODEL=gpt-4o-mini
# 可选
# export DRAMA_FORGE_PROVIDER_TIMEOUT=30
# export DRAMA_FORGE_PROVIDER_ID=openai-compatible
# export DRAMA_FORGE_PROVIDER_CHAT_PATH=v1/chat/completions
# export DRAMA_FORGE_PROVIDER_DRY_RUN=1
```

## 说明

- 若 `base_url` 已以 `/v1` 结尾，路径拼接不会重复 `/v1`
- `chat_path` 可配置，以兼容与 OpenAI 布局不同的厂商
- 缺 Key 或 dry-run → 确定性离线回退
- DeepSeek 预设也建立在此适配器之上

## 参见

- [LLM Providers 总览](../LLM_PROVIDERS.zh-CN.md)
- [DeepSeek](deepseek.zh-CN.md)

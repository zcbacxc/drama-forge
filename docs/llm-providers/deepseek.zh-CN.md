[![English](https://img.shields.io/badge/English-DeepSeek-blue)](deepseek.md)
[![简体中文](https://img.shields.io/badge/简体中文-DeepSeek-green)](deepseek.zh-CN.md)

# DeepSeek

DeepSeek 通过共享的 **OpenAI-compatible** 适配器接入（没有厂商专属生产图）。

## 能力

- `text_generation`

## 环境变量

```bash
export DRAMA_FORGE_PROVIDER=deepseek
# 或：export DRAMA_FORGE_PROVIDER=production   # deepseek + siliconflow

export DRAMA_FORGE_DEEPSEEK_API_KEY=sk-...
# 可选覆盖
# export DRAMA_FORGE_DEEPSEEK_BASE_URL=https://api.deepseek.com
# export DRAMA_FORGE_DEEPSEEK_MODEL=deepseek-flash
# export DRAMA_FORGE_DEEPSEEK_TIMEOUT=60
# export DRAMA_FORGE_DEEPSEEK_CHAT_PATH=chat/completions
# export DRAMA_FORGE_PROVIDER_DRY_RUN=1
```

## 说明（live 已验证预设）

- Chat path 为 `chat/completions`（不是 `/v1/chat/completions`）
- 默认模型为 `deepseek-flash`（可用 `DRAMA_FORGE_DEEPSEEK_MODEL` 覆盖）
- `content` 为空时，共享适配器可能回退到 `reasoning_content`
- 缺 Key 或 dry-run 时返回确定性离线回退结果

## 不改生产图的钉选方式

```python
policy = {"by_capability": {"text_generation": {"provider_id": "deepseek"}}}
result = engine.run(story, provider_policy=policy)
```

## 参见

- [LLM Providers 总览](../LLM_PROVIDERS.zh-CN.md)
- [OpenAI-compatible](openai-compatible.zh-CN.md)
- [架构](../ARCHITECTURE.zh-CN.md)

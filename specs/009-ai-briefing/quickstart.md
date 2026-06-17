# Quickstart: F7 AI 早盘简报

**Feature**: specs/009-ai-briefing  
**Date**: 2026-06-17

---

## 1. 环境要求

- 已完成 MVP 环境搭建（`backend/setup.sh`）
- 已配置 LLM API 密钥（以下任选其一）：
  - `OPENAI_API_KEY`
  - `DEEPSEEK_API_KEY`
- 已配置推送通道（飞书或 Telegram 至少一个）
- Redis 可选（008 已引入，不可用时会降级为 SQLite 缓存）

## 2. 配置说明

在 `backend/.env` 中新增：

```env
# LLM 配置（至少配置一个）
OPENAI_API_KEY=sk-xxx
OPENAI_MODEL=gpt-4o-mini
# DEEPSEEK_API_KEY=sk-xxx
# DEEPSEEK_MODEL=deepseek-chat

# 简报生成开关
BRIEFING_ENABLED=true
BRIEFING_GENERATION_HOUR=8
BRIEFING_GENERATION_MINUTE=50
BRIEFING_PUSH_HOUR=9
BRIEFING_PUSH_MINUTE=0

# 超时与重试
BRIEFING_LLM_TIMEOUT_SECONDS=30
BRIEFING_LLM_RETRY_INTERVAL_SECONDS=5
BRIEFING_TOTAL_TIMEOUT_SECONDS=60
BRIEFING_MAX_RETRIES=2

# 手动刷新冷却期
BRIEFING_MANUAL_COOLDOWN_SECONDS=30
```

## 3. 验证简报生成

### 3.1 手动触发

```bash
cd backend
curl -X POST http://127.0.0.1:8000/api/briefing/generate \
  -H "Content-Type: application/json" \
  -d '{}'
```

### 3.2 查看最新简报

```bash
curl http://127.0.0.1:8000/api/briefing/latest
```

### 3.3 检查推送日志

```bash
curl http://127.0.0.1:8000/push/logs
```

## 4. 本地测试 LLM

```bash
cd backend
.venv/bin/python -c "
from backend.app.services.briefing_llm_client import BriefingLLMClient
client = BriefingLLMClient()
result = client.generate('测试 prompt')
print(result)
"
```

## 5. 常见问题

**Q: 简报没有生成？**  
A: 检查是否为交易日、是否配置 LLM 密钥、日志中是否有错误。

**Q: LLM 失败会通知我吗？**  
A: 会降级为模板简报并推送，Dashboard 推送历史中可看到降级状态。

**Q: 手动刷新提示冷却期？**  
A: 手动刷新有 30 秒冷却期，请稍后再试。

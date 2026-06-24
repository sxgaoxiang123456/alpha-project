# Quickstart: F8 自然语言设预警

**Feature**: specs/010-natural-language-alert  
**Date**: 2026-06-17

---

## 1. 环境要求

- 已完成 MVP 环境搭建（`backend/setup.sh`）
- 已启动 FastAPI 服务（`cd backend && .venv/bin/python -m uvicorn app.main:app`）
- LLM 兜底为可选：配置 `OPENAI_API_KEY` 或 `DEEPSEEK_API_KEY` 后支持复杂/同义表达；未配置时仅使用规则解析

## 2. 配置说明

在 `backend/.env` 中新增（可选）：

```env
# LLM 兜底配置（至少配置一个以启用 LLM 兜底）
OPENAI_API_KEY=sk-xxx
OPENAI_MODEL=gpt-4o-mini
# DEEPSEEK_API_KEY=sk-xxx
# DEEPSEEK_MODEL=deepseek-chat

# 解析置信度阈值（可选，默认 0.7）
NL_ALERT_CONFIDENCE_THRESHOLD=0.7
```

## 3. 验证自然语言创建预警

### 3.1 标准价格预警

```bash
cd backend
curl -X POST http://127.0.0.1:8000/alerts/natural-language \
  -H "Content-Type: application/json" \
  -d '{"query": "茅台跌破 1500 提醒我"}'
```

### 3.2 涨跌幅预警

```bash
curl -X POST http://127.0.0.1:8000/alerts/natural-language \
  -H "Content-Type: application/json" \
  -d '{"query": "茅台涨幅超过 2% 提醒我"}'
```

### 3.3 歧义候选

```bash
curl -X POST http://127.0.0.1:8000/alerts/natural-language \
  -H "Content-Type: application/json" \
  -d '{"query": "银行跌破 10 元提醒我"}'
```

返回候选后，选择招商银行重新提交：

```bash
curl -X POST http://127.0.0.1:8000/alerts/natural-language \
  -H "Content-Type: application/json" \
  -d '{"query": "银行跌破 10 元提醒我", "selected_stock_code": "600036"}'
```

### 3.4 低置信度输入

```bash
curl -X POST http://127.0.0.1:8000/alerts/natural-language \
  -H "Content-Type: application/json" \
  -d '{"query": "帮我看着点茅台"}'
```

## 4. 查看预警规则

```bash
curl http://127.0.0.1:8000/alerts
```

## 5. 常见问题

**Q: 未配置 LLM API Key 能否使用？**  
A: 可以。规则解析器覆盖核心句式，未配置 LLM 时复杂/同义表达会返回低置信度提示。

**Q: 输入歧义后如何选择候选？**  
A: 前端会展示候选列表，点击后自动携带 `selected_stock_code` 重新提交；curl 测试需手动填充该字段。

**Q: 置信度阈值可以调整吗？**  
A: 可通过 `NL_ALERT_CONFIDENCE_THRESHOLD` 调整，默认 0.7。

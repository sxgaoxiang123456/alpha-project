# Research Notes: F7 AI 早盘简报

**Feature**: specs/009-ai-briefing  
**Date**: 2026-06-17  
**Purpose**: 记录 F7 实现所需的技术选型与决策依据

---

## 1. LLM Provider 选型

### Decision
使用 **DeepSeek-V4-Flash** 作为唯一 LLM，通过 `https://api.deepseek.com` 调用，OpenAI 兼容接口。

### Rationale
- v1.1 启动前已决策统一使用 DeepSeek 方案，简化配置和运维
- DeepSeek-V4-Flash 成本低、国内访问稳定、支持 JSON Output，适合结构化简报生成
- 不引入 OpenAI/Anthropic SDK，降低依赖；用 `httpx` 直接调用 OpenAI 兼容接口
- 单用户 + 每日 1 次早盘简报 + 低频兜底调用，预计月均成本 < 10 元，符合年运营预算 ≤ 1000 元

### Configuration
- API key 通过 `backend/.env` 的 `DEEPSEEK_API_KEY` 配置（v1.1 不引入 Settings 数据库存储）
- 模型名固定为 `deepseek-v4-flash`，基础 URL 默认 `https://api.deepseek.com`
- 超时/重试参数可在 `.env` 调整：`DEEPSEEK_TIMEOUT_SECONDS=30`、`DEEPSEEK_RETRY_ATTEMPTS=3`、`DEEPSEEK_RETRY_INTERVAL_SECONDS=5`

### Alternatives Considered
- OpenAI GPT-4o-mini：国际模型，国内访问需代理，配置复杂
- Claude 3.5 Haiku：未纳入主选，因当前项目未引入 Anthropic SDK
- 本地模型（Ollama）：部署复杂、硬件成本高，不符合零成本起步原则
- 金融专用大模型（HithinkGPT 等）：生态不成熟，接入成本高

---

## 2. Prompt 管理

### Decision
Prompt 模板以 **Jinja2 文件**形式存放在 `backend/app/templates/prompts/briefing.j2`，运行时加载。

### Rationale
- 项目已使用 Jinja2 作为模板引擎，技术栈一致
- 模板文件便于迭代和 A/B 测试，无需改代码
- 避免将长 Prompt 硬编码在 Python 中

---

## 3. LLM 调用方式

### Decision
使用 **同步 HTTP 客户端（httpx）**直接调用 DeepSeek OpenAI 兼容接口，配合 APScheduler 执行。

### Rationale
- DeepSeek 提供 OpenAI 兼容接口，无需引入 `openai` SDK，用 `httpx` 即可构造请求
- 项目现有 APScheduler BackgroundScheduler 已用于行情刷新和简报推送
- 简报生成不需要实时响应用户请求，适合后台任务
- 同步调用配合 timeout 控制更简单，避免 async 与 sync SQLAlchemy session 的复杂交互
- 未来若需高并发或切换 provider 可再迁移到异步/抽象层

---

## 4. 异动计算方案

### Decision
使用 **pandas/numpy** 基于 `HistoricalQuote` 表数据计算：
- 涨速：当前价 vs N 日收盘价变化率
- 成交量突增：当前成交量 vs N 日均量倍数

### Rationale
- 项目后端已依赖 pandas（AkShare/BaoStock 返回 DataFrame）
- 历史行情已落盘 90 天，可直接查询
- 规则透明、可解释，符合盯盘场景需求

---

## 5. 简报存储

### Decision
简报内容**不持久化到独立表**，仅作为最新一条缓存到 Redis（或 SQLite CacheEntry）。

### Rationale
- v1.1 仅展示「最近一条」简报，无需历史详情页
- 推送日志（PushLog）已记录发送状态，满足审计需求
- 减少数据模型复杂度，符合 MVP 约束

---

## 6. 与现有系统的集成

| 现有模块 | 复用方式 |
|---|---|
| `MarketIndexService` | 获取大盘指数 |
| `QuoteService` / `DataSourceFacade` | 获取实时行情、历史行情 |
| `PushService` | 发送简报卡片/文本 |
| `QuoteScheduler` | 注册 8:50 定时任务 |
| `HistoricalQuote` | 读取 N 日历史数据 |
| `AlertTrigger` | 读取过去 24 小时预警记录 |
| `trading_calendar.is_trading_day()` | 判断是否为交易日 |
| Redis Cache（008 引入） | 缓存最新简报 |

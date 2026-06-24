# Data Model: F7 AI 早盘简报

**Feature**: specs/009-ai-briefing  
**Date**: 2026-06-17

---

## 1. 实体清单

本 feature 不新增持久化数据库表，仅新增**运行时缓存键**和**Prompt 模板文件**。简报生成结果通过现有 `PushLog` 记录发送历史，通过 Redis/SQLite 缓存最新一条简报内容供 Dashboard 展示。

### 1.1 Briefing（简报）—— 运行时缓存对象

| 字段 | 类型 | 说明 |
|---|---|---|
| `date` | date | 简报日期 |
| `generated_at` | datetime | 生成时间 |
| `market_indices` | dict | 大盘指数快照 |
| `top_movers` | list[dict] | 异动 TOP 5 |
| `insights` | list[str] | AI 自然语言解读要点 |
| `is_degraded` | bool | 是否为模板降级 |
| `degraded_reason` | str | 降级原因（如 LLM 失败、超时） |

**缓存键**：`latest_briefing`  
**TTL**：300 秒（与行情缓存周期对齐）

### 1.2 TopMover（异动股票）

| 字段 | 类型 | 说明 |
|---|---|---|
| `code` | str | 股票代码 |
| `name` | str | 股票名称 |
| `type` | str | 异动类型：volume_surge / price_surge / both |
| `value` | float | 异动数值（如涨速 % 或均量倍数） |
| `threshold` | float | 触发阈值 |
| `sector` | str | 所属板块 |
| `insight` | str | 一句话解读 |
| `data_quality` | str | 数据质量：normal / insufficient_history |

### 1.3 MarketIndexSnapshot（大盘指数快照）

复用现有 `MarketIndexService` 输出，结构如下：

| 字段 | 类型 | 说明 |
|---|---|---|
| `name` | str | 指数名称 |
| `current_value` | float | 当前点位 |
| `change_percent` | float | 涨跌幅 |
| `change_amount` | float | 涨跌额 |

### 1.4 PromptTemplate（提示模板）

以文件形式存储，非数据库实体：

| 文件 | 路径 | 说明 |
|---|---|---|
| `briefing.j2` | `backend/app/templates/prompts/briefing.j2` | LLM 输入模板 |

---

## 2. 与现有数据模型的关系

```
WatchlistItem ──► 自选股代码列表
       │
       ▼
HistoricalQuote ──► N 日历史行情 ──► TopMover 计算
       ▲
DataSourceFacade ──► 实时行情
       │
MarketIndexService ──► 大盘指数
       │
AlertTrigger ──► 过去 24 小时预警记录
       │
       ▼
PromptTemplate + LLM ──► Briefing 运行时对象
       │
       ▼
PushService ──► PushLog
       │
       ▼
Redis Cache ──► latest_briefing
```

---

## 3. 验证规则

- `date` 必须是交易日
- `top_movers` 长度 0-5
- `market_indices` 必须包含上证指数、深证成指、创业板指
- `insights` 长度 1-5 条
- `value` 必须为非空数值
- `code` 必须是 6 位 A 股代码

---

## 4. 状态说明

| 状态 | 含义 |
|---|---|
| `generated` | 已生成但未推送 |
| `sent` | 已成功推送 |
| `fallback` | 主通道失败，已用备用通道推送 |
| `degraded` | LLM 失败，已发送模板简报 |
| `failed` | 双通道均失败 |

> 注：具体推送状态由 `PushLog.status` 字段记录，简报对象本身只记录 `is_degraded`。

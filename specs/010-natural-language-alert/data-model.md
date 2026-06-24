# Data Model: F8 自然语言设预警

**Feature**: specs/010-natural-language-alert  
**Date**: 2026-06-17

---

## 说明

F8 为自然语言创建预警规则的功能层，**不新增持久化数据库表**。所有运行时对象均为 Pydantic 模型，用于 API 请求/响应和解析结果传递。持久化规则复用 MVP 的 `AlertRule` 模型。

---

## 运行时对象

### NaturalLanguageQuery（自然语言查询）

用户输入的原始文本及上下文。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `query` | str | 是 | 用户输入的自然语言，如「茅台跌破 1500 提醒我」 |
| `selected_stock_code` | str | 否 | 歧义候选确认后前端携带的指定股票代码 |
| `submitted_at` | datetime | 是 | 提交时间，用于日志和性能统计 |

---

### ParsedAlertIntent（解析后的预警意图）

规则解析器或 LLM 输出的结构化意图。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `stock_code` | str | 条件 | 6 位 A 股代码；歧义时为空 |
| `stock_name` | str | 条件 | 股票名称；歧义时为空 |
| `condition_type` | str | 条件 | `price_above` / `price_below` / `change_pct_above` / `change_pct_below`；不确定时为空 |
| `threshold` | float | 条件 | 阈值；价格条件为价格，涨跌幅条件为百分比点数（带符号）；不确定时为空 |
| `confidence` | float | 是 | 解析置信度，0.0 ~ 1.0 |
| `ambiguity` | bool | 是 | 是否处于股票名称歧义状态 |
| `candidates` | list[StockCandidate] | 否 | 歧义时返回的候选列表 |
| `unsupported_condition` | str | 否 | 识别到但不支持的条件类型描述，如「成交量」 |
| `message` | str | 否 | 解析过程中的补充说明或错误提示 |

**状态规则**：
- 唯一匹配：stock_code 有值，ambiguity=false
- 名称歧义：stock_code 为空，ambiguity=true，candidates 有值
- 无法匹配：stock_code 为空，ambiguity=false
- 低置信度：confidence < 0.7 时拒绝创建

---

### StockCandidate（股票候选）

歧义时返回给前端的候选对象。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `stock_code` | str | 是 | 6 位 A 股代码 |
| `stock_name` | str | 是 | 股票名称 |
| `sector` | str | 否 | 所属行业 |
| `market_cap` | float | 否 | 总市值（亿元），用于排序 |
| `match_score` | float | 是 | 名称相似度分数，0.0 ~ 1.0 |

**排序规则**：
1. 按 `match_score` 降序
2. 同分段按 `market_cap` 降序
3. 最多返回 10 条

---

### NaturalLanguageAlertResponse（API 响应）

统一 API 响应结构。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `success` | bool | 是 | 是否成功创建规则 |
| `rule` | AlertRuleSummary | 否 | 创建成功后的规则摘要 |
| `message` | str | 是 | 操作结果提示 |
| `candidates` | list[StockCandidate] | 否 | 歧义时返回候选列表 |

### AlertRuleSummary（规则摘要）

创建成功后返回的精简规则信息。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `stock_code` | str | 是 | 6 位 A 股代码 |
| `stock_name` | str | 是 | 股票名称 |
| `condition_type` | str | 是 | 条件类型 |
| `threshold` | float | 是 | 阈值 |

---

## 持久化复用

### AlertRule（MVP 已有）

创建成功后写入 `backend/app/models/alert_rule.py` 定义的表。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | int | 主键 |
| `stock_code` | str | 6 位 A 股代码 |
| `condition_type` | str | 条件类型 |
| `threshold` | float | 阈值 |
| `cooldown_minutes` | int | 冷却期（分钟） |
| `created_at` | datetime | 创建时间 |
| `updated_at` | datetime | 更新时间 |

F8 不修改 `AlertRule` 表结构，仅通过现有 service 写入。

---

## 状态流转

```
用户提交 query
    │
    ▼
输入校验
    │
    ├── 失败 ──→ 返回错误 message
    │
    ▼
解析 (规则 → LLM 兜底)
    │
    ├── 置信度 < 0.7 ──→ 返回「未能理解」
    │
    ▼
股票匹配
    │
    ├── 歧义 ──→ 返回 candidates
    │   │
    │   ▼
    │ 用户选择 ──→ 携带 stock_code 重新提交
    │
    ├── 无法匹配 ──→ 返回无匹配
    │
    ▼
规则校验
    │
    ├── 失败 ──→ 返回具体错误
    │
    ▼
创建 AlertRule ──→ 返回成功
```

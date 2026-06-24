# Data Model: F9 成交量异动检测

**Feature**: specs/011-volume-surge-alert  
**Date**: 2026-06-17

---

## 新增数据库表

### `volume_surge_events`

每个成交量异动事件一条记录。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | Integer | 是 | 主键，自增 |
| `stock_code` | String(6) | 是 | 6 位 A 股代码 |
| `stock_name` | String(32) | 是 | 股票名称 |
| `date` | Date | 是 | 触发日期 |
| `volume` | BigInteger | 是 | 当日成交量（股） |
| `avg_volume` | Float | 是 | 前 N 个交易日平均成交量（股） |
| `ratio` | Float | 是 | 当日成交量 / 均量 |
| `threshold` | Float | 是 | 触发倍数阈值 M |
| `window_days` | Integer | 是 | 计算窗口 N |
| `data_quality` | String(16) | 是 | `normal` 或 `limited`（历史数据不足时） |
| `triggered_at` | DateTime | 是 | 事件生成时间 |
| `pushed_at` | DateTime | 否 | 推送时间 |
| `created_at` | DateTime | 是 | 记录创建时间 |

**唯一约束**：`(stock_code, date)` 唯一，保证同一股票同一天只触发一次。

---

## 复用现有设置机制

### `VolumeSurgeSetting`

通过现有 `settings` 键值对机制持久化，无需新建表。

| 设置键 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `volume_surge_enabled` | bool | true | 检测开关 |
| `volume_surge_window_days` | int | 20 | 历史均量窗口 |
| `volume_surge_multiplier` | float | 2.0 | 异动倍数阈值 |
| `volume_surge_cooldown_days` | int | 1 | 冷却期 |

---

## 运行时对象

### VolumeSurgeDetectRequest

手动触发检测时的请求对象。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `force` | bool | 否 | 是否忽略交易日判断强制检测 |

### VolumeSurgeEventResponse

API 返回的异动事件对象。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `stock_code` | str | 是 | 6 位 A 股代码 |
| `stock_name` | str | 是 | 股票名称 |
| `date` | str | 是 | 触发日期（YYYY-MM-DD） |
| `volume` | int | 是 | 当日成交量 |
| `avg_volume` | float | 是 | 前 N 日均量 |
| `ratio` | float | 是 | 倍数 |
| `threshold` | float | 是 | 触发阈值 |
| `data_quality` | str | 是 | `normal` / `limited` |
| `triggered_at` | str | 是 | ISO 8601 时间 |

### TodayVolumeSurgeResponse

Dashboard 今日异动接口返回对象。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `success` | bool | 是 | 是否成功 |
| `data` | object | 是 | `{ date, total, top_5, has_more }` |
| `message` | str | 是 | 提示信息 |

---

## 状态流转

```
每个交易日 15:15（或手动触发）
    │
    ▼
读取设置（enabled / window_days / multiplier / cooldown_days）
    │
    ▼
enabled == false ?
    ├── 是 ──→ 跳过
    └── 否 ──→ 继续
    │
    ▼
读取 watchlist
    │
    ▼
循环每只股票：
    ├── 停牌？跳过
    ├── 拉取历史成交量
    ├── 数据不足？标记 limited
    ├── ratio >= multiplier？
    │       ├── 否 ──→ 跳过
    │       └── 是 ──→ 检查 (stock_code, date) 是否已存在
    │               ├── 存在 ──→ 跳过（冷却期去重）
    │               └── 不存在 ──→ 写入 volume_surge_events
    │
    ▼
查询当日所有事件
    │
    ▼
排序取 Top 5
    │
    ▼
push_message 发送
```

---

## 与现有模型的关系

- `VolumeSurgeEvent` 不依赖 `AlertRule`，是独立的检测事件。
- `PushLog` 记录 `volume_surge` 类型的推送，与事件解耦。
- `Watchlist` 提供监控股票代码列表。
- `HistoricalQuote` 提供历史成交量数据。

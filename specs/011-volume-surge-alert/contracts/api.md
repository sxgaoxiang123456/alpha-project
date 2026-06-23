# API Contract: F9 成交量异动检测

**Feature**: specs/011-volume-surge-alert  
**Date**: 2026-06-17

---

## 1. 手动触发检测

### Endpoint

```
POST /api/volume-surge/detect
```

### Request

**Headers**:

| Header | Value | Required |
|---|---|---|
| `Content-Type` | `application/json` | Yes |

**Body**:

```json
{
  "force": false
}
```

| Field | Type | Default | Description |
|---|---|---|---|
| `force` | bool | false | 是否忽略交易日判断强制检测 |

### Response

**Success (200 OK)**

```json
{
  "success": true,
  "message": "检测完成，今日发现 3 只自选股成交量异动",
  "data": {
    "date": "2026-06-17",
    "total": 3,
    "top_5": [
      {
        "stock_code": "600519",
        "stock_name": "贵州茅台",
        "date": "2026-06-17",
        "volume": 1500000,
        "avg_volume": 500000,
        "ratio": 3.0,
        "threshold": 2.0,
        "data_quality": "normal",
        "triggered_at": "2026-06-17T15:15:23"
      }
    ],
    "has_more": false
  }
}
```

**No Surge (200 OK)**

```json
{
  "success": true,
  "message": "检测完成，今日无成交量异动",
  "data": {
    "date": "2026-06-17",
    "total": 0,
    "top_5": [],
    "has_more": false
  }
}
```

**Disabled (200 OK with success=false)**

```json
{
  "success": false,
  "message": "成交量异动检测已关闭，请在设置中开启"
}
```

**Non-Trading Day (422 Unprocessable Entity)**

```json
{
  "success": false,
  "message": "今日非交易日，无需检测"
}
```

**Internal Error (500 Internal Server Error)**

```json
{
  "success": false,
  "message": "检测失败，请查看系统日志"
}
```

---

## 2. 获取今日异动列表

### Endpoint

```
GET /api/volume-surge/today
```

### Response

**Success (200 OK)**

```json
{
  "success": true,
  "message": "",
  "data": {
    "date": "2026-06-17",
    "total": 7,
    "top_5": [
      {
        "stock_code": "600519",
        "stock_name": "贵州茅台",
        "date": "2026-06-17",
        "volume": 1500000,
        "avg_volume": 500000,
        "ratio": 3.0,
        "threshold": 2.0,
        "data_quality": "normal",
        "triggered_at": "2026-06-17T15:15:23"
      }
    ],
    "has_more": true
  }
}
```

**No Data (200 OK)**

```json
{
  "success": true,
  "message": "今日无成交量异动",
  "data": {
    "date": "2026-06-17",
    "total": 0,
    "top_5": [],
    "has_more": false
  }
}
```

---

## 3. 获取全部异动列表（分页）

### Endpoint

```
GET /api/volume-surge/events?date=2026-06-17&limit=50&offset=0
```

### Query Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `date` | str | 今日 | 过滤日期，格式 YYYY-MM-DD |
| `limit` | int | 50 | 每页数量，最大 100 |
| `offset` | int | 0 | 分页偏移 |

### Response

**Success (200 OK)**

```json
{
  "success": true,
  "data": {
    "date": "2026-06-17",
    "total": 7,
    "items": [
      {
        "stock_code": "600519",
        "stock_name": "贵州茅台",
        "date": "2026-06-17",
        "volume": 1500000,
        "avg_volume": 500000,
        "ratio": 3.0,
        "threshold": 2.0,
        "data_quality": "normal",
        "triggered_at": "2026-06-17T15:15:23"
      }
    ],
    "limit": 50,
    "offset": 0
  }
}
```

---

## 4. 更新检测设置

### Endpoint

```
PUT /api/settings/volume-surge
```

### Request Body

```json
{
  "enabled": true,
  "window_days": 20,
  "multiplier": 2.0,
  "cooldown_days": 1
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `enabled` | bool | 否 | 检测开关 |
| `window_days` | int | 否 | 5/10/20/60 |
| `multiplier` | float | 否 | 1.5/2.0/3.0/5.0 |
| `cooldown_days` | int | 否 | 1/3/5 |

### Response

**Success (200 OK)**

```json
{
  "success": true,
  "message": "设置已保存",
  "data": {
    "enabled": true,
    "window_days": 20,
    "multiplier": 2.0,
    "cooldown_days": 1
  }
}
```

**Invalid Value (422 Unprocessable Entity)**

```json
{
  "detail": [
    {
      "loc": ["body", "window_days"],
      "msg": "时间窗口仅支持 5/10/20/60",
      "type": "value_error"
    }
  ]
}
```

---

## 5. Dashboard 组件契约

组件文件：`frontend/src/templates/components/volume_surge_card.html`

**行为**：

1. 页面加载时调用 `GET /api/volume-surge/today` 获取今日 Top 5
2. 点击「立即检测」按钮调用 `POST /api/volume-surge/detect`
3. 检测完成后刷新卡片内容
4. 当 `has_more=true` 时显示「查看全部」入口，点击进入完整列表页或弹窗

**展示字段**：

| 字段 | 说明 |
|---|---|
| `stock_name` | 股票名称 |
| `stock_code` | 股票代码 |
| `ratio` | 成交量倍数 |
| `volume` | 当日成交量 |
| `avg_volume` | N 日均量 |

**空状态**：

- 今日无异动时显示「今日无成交量异动」
- 检测关闭时显示「成交量异动检测已关闭」

---

## 6. 推送消息格式

**消息类型**：`volume_surge`

**单只股票示例**：

```
成交量异动：贵州茅台（600519）今日成交量 3.0 倍于 20 日均量
```

**多只汇总示例（最多 5 只）**：

```
今日成交量异动 Top 3：
1. 贵州茅台（600519）3.0 倍
2. 招商银行（600036）2.8 倍
3. 五粮液（000858）2.5 倍
```

---

## 7. 定时任务契约

- **任务名称**: `detect_volume_surge_if_trading_day`
- **触发时间**: 每个交易日 15:15
- **执行逻辑**: 判断是否为交易日 → 读取设置 → 若开启则执行检测 → 若有事件则推送 Top 5
- **幂等性**: 通过 `(stock_code, date)` 唯一约束保证同一股票同一天只记录一次

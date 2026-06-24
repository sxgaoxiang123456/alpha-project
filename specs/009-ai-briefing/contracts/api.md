# API Contract: F7 AI 早盘简报

**Feature**: specs/009-ai-briefing  
**Date**: 2026-06-17

---

## 1. 手动触发简报生成

### Endpoint

```
POST /api/briefing/generate
```

### Request

**Headers**:

| Header | Value | Required |
|---|---|---|
| `Content-Type` | `application/json` | Yes |

**Body**: 空对象 `{}` 或可选参数

```json
{
  "force": false
}
```

| Field | Type | Default | Description |
|---|---|---|---|
| `force` | bool | false | 是否忽略 30 秒手动刷新冷却期 |

### Response

**Success (200 OK)**

```json
{
  "success": true,
  "message": "简报生成已触发",
  "data": {
    "briefing_id": "uuid",
    "status": "pending",
    "estimated_seconds": 30
  }
}
```

**Cooldown (429 Too Many Requests)**

```json
{
  "success": false,
  "message": "简报刷新过于频繁，请稍后再试",
  "data": {
    "retry_after_seconds": 18
  }
}
```

**Non-Trading Day (422 Unprocessable Entity)**

```json
{
  "success": false,
  "message": "今日非交易日，暂无简报"
}
```

**Internal Error (500 Internal Server Error)**

```json
{
  "success": false,
  "message": "简报生成失败，请查看系统日志"
}
```

---

## 2. 获取最新简报

### Endpoint

```
GET /api/briefing/latest
```

### Response

**Success (200 OK)**

```json
{
  "success": true,
  "data": {
    "date": "2026-06-17",
    "generated_at": "2026-06-17T08:51:23",
    "is_degraded": false,
    "market_indices": {
      "上证指数": { "current": 3350.12, "change_pct": 0.23 },
      "深证成指": { "current": 10150.88, "change_pct": 0.45 },
      "创业板指": { "current": 2035.67, "change_pct": 0.67 }
    },
    "top_movers": [
      {
        "code": "600519",
        "name": "贵州茅台",
        "type": "volume_surge",
        "value": 3.2,
        "threshold": 2.0,
        "sector": "白酒",
        "insight": "成交量突增 3.2 倍，资金关注度提升",
        "data_quality": "normal"
      }
    ],
    "insights": [
      "大盘整体偏暖，消费板块资金流入明显",
      "半导体板块出现分化，注意高位风险"
    ]
  }
}
```

**No Briefing (404 Not Found)**

```json
{
  "success": false,
  "message": "今日暂无简报"
}
```

---

## 3. Dashboard 页面更新

- Dashboard 首页 `briefing_card.html` 组件通过 `GET /api/briefing/latest` 获取数据
- 点击「重新生成简报」按钮调用 `POST /api/briefing/generate`
- 生成成功后前端轮询 `/api/briefing/latest` 直至获取到新数据

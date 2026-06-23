# Quickstart: F9 成交量异动检测

**Feature**: specs/011-volume-surge-alert  
**Date**: 2026-06-17

---

## 1. 环境要求

- 已完成 MVP 环境搭建（`backend/setup.sh`）
- 已启动 FastAPI 服务
- 已添加至少 1 只自选股
- 推送通道（飞书或 Telegram）至少配置一个（用于接收异动推送）

## 2. 配置说明

在 `backend/.env` 中新增（可选，默认已启用）：

```env
# 成交量异动检测开关（可选，默认 true）
VOLUME_SURGE_ENABLED=true

# 检测时间（可选，默认 15:15）
VOLUME_SURGE_DETECT_HOUR=15
VOLUME_SURGE_DETECT_MINUTE=15
```

设置项通过 `/api/settings/volume-surge` 持久化，优先级高于 `.env` 默认值。

## 3. 验证成交量异动检测

### 3.1 查看今日异动

```bash
cd backend
curl http://127.0.0.1:8000/api/volume-surge/today
```

### 3.2 手动触发检测

```bash
curl -X POST http://127.0.0.1:8000/api/volume-surge/detect \
  -H "Content-Type: application/json" \
  -d '{}'
```

非交易日强制检测：

```bash
curl -X POST http://127.0.0.1:8000/api/volume-surge/detect \
  -H "Content-Type: application/json" \
  -d '{"force": true}'
```

### 3.3 更新检测设置

```bash
curl -X PUT http://127.0.0.1:8000/api/settings/volume-surge \
  -H "Content-Type: application/json" \
  -d '{"enabled": true, "window_days": 20, "multiplier": 2.0, "cooldown_days": 1}'
```

### 3.4 查看全部异动事件

```bash
curl "http://127.0.0.1:8000/api/volume-surge/events?date=2026-06-17&limit=50"
```

### 3.5 检查推送日志

```bash
curl http://127.0.0.1:8000/push/logs
```

## 4. 常见问题

**Q: 检测没有执行？**  
A: 检查是否为交易日、检测开关是否开启、自选股是否为空、日志中是否有数据源错误。

**Q: 收到重复推送？**  
A: 检查 `volume_surge_events` 表唯一约束 `(stock_code, date)` 是否存在。

**Q: Dashboard 卡片看不到数据？**  
A: 先手动触发检测，再调用 `/api/volume-surge/today` 查看是否有事件。

**Q: 停牌股被误判？**  
A: 停牌判断基于「当日成交量为 0 且收盘价等于昨收」，请确认数据源返回正确日 K。

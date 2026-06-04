# 会话交接 · 基础实时行情

## 上次做到哪
Feature 003 已全部完成。15 个 task 全绿（244 tests passed），代码审查发现 3 Critical + 5 Important，全部修复完毕。

## 修复内容
1. C1: AkShare/BaoStock 适配器添加 `status` 字段转发 → 停牌检测可用
2. C2: MarketIndexService._decimal() 增加 None 值保护
3. C3: main.py 添加 HistoricalQuote 90 天清理定时任务（每日 3:07）
4. I1: 提取 trading_calendar.py，集成 AkShare 交易日历 + 工作日降级
5. I2: 5 个新模块添加 logging（data_cleaner/quote_service/quote_scheduler/market_index/quotes router）
6. I3: 缓存命中 + 非交易时段 → 标记 market_closed
7. I5: 缓存命中 → source_status="cached"

## 新增文件
- `backend/app/core/trading_calendar.py` — 交易日历 + 交易时段判断

## 修改文件
- `backend/app/services/data_source.py` — +status 字段
- `backend/app/services/market_index.py` — _decimal None 保护 + logging
- `backend/app/main.py` — HistoricalQuote 清理任务 + trading_calendar 导入
- `backend/app/routers/quotes.py` — market_closed + source_status cached + logging
- `backend/app/services/data_cleaner.py` — logging
- `backend/app/services/quote_service.py` — logging + 异步落盘异常捕获
- `backend/app/core/quote_scheduler.py` — logging
- `backend/tests/integration/test_quotes_api.py` — 适配 source_status="cached"

## 下一步
- merge 回 main → tag v0.2.0-003-realtime-quotes
- 可以开始 F4 价格预警（004-price-alert）

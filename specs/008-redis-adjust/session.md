# 008-redis-adjust · 会话记录

## 完成摘要

Dashboard 性能优化 feature 全部完成。16 个 task（T1-T16）+ Step 4 code review + Step 5 收尾全部通过。

## 核心交付

| 模块 | 文件 | 功能 |
|:---|:---|:---|
| Redis 缓存 | `backend/app/core/redis_cache.py` | 连接管理、get/set/delete、JSON 序列化、降级返回 None |
| 异步落盘 | `backend/app/core/async_persistence.py` | asyncio.to_thread() 后台 SQLite 写入 |
| 行情缓存 | `backend/app/services/quote_service.py` | use_cache 参数，Redis 优先，TTL=60s |
| 大盘缓存 | `backend/app/services/market_index.py` | use_cache 参数，Redis 优先 |
| 并行查询 | `backend/app/services/dashboard_service.py` | asyncio.gather() + 独立 session |
| Partial 路由 | `backend/app/routers/dashboard.py` | /market_data 只返回行情，ETag/304 |
| 骨架屏 | `frontend/src/templates/components/skeleton_screen.html` | Tailwind animate-pulse |
| ETag JS | `frontend/public/js/dashboard.js` | If-None-Match、304 跳过、降级检测 |
| Docker | `docker-compose.yml` | Redis 7-alpine + healthcheck |

## Code Review 结果

| 类别 | 数量 | 处置 |
|:---|:---|:---|
| Critical | 3 | 全部修复 |
| Important | 8 | 6 修复 + 2 Push back |
| Minor | 9 | Deferred |

**修复详情：**
1. MD5 → SHA-256（ETag 安全）
2. DataSourceFacade 类级数据源缓存（避免每请求创建实例）
3. 历史持久化改为 threading.Thread 后台执行
4. market_index actual_timestamp 缓存/恢复
5. quote_service 缓存 key 排序确保稳定
6. dashboard.js 添加完整 ETag/304 支持

## 测试状态

- 单元 + 集成测试：`542 passed, 0 failed`
- E2E 测试：`47 passed, 1 skipped`
- 合计：`589 passed, 1 skipped`

> 注：E2E 中 `test_market_container_stable_size` 因 `#market-data-container` 使用 `contents` 布局无法获取 bounding_box，属已知限制；其余全部通过。

## 已知问题（Deferred）

1. Redis TTL 硬编码（60s/300s），未集中配置
2. docker-compose.yml Redis maxmemory=100mb 对高负载可能不足
3. quote_service 缓存命中时未二次运行 DataCleaner（依赖写入方保证数据清洗）

## 收尾修复

1. **ETag/304 接缝测试兼容实时行情**（commit `becb006`）
   - 真实行情在两次 `/market_data` 请求之间可能变化，导致原有断言要求"必须 304"出现偶发失败。
   - 将 `test_304_response_has_no_body`、`test_if_none_match_header_forwarded` 改为分支断言：
     - 304 时验证 body 为空且 ETag 不变；
     - 200 时验证 body 非空且 ETag 已变化。
   - `test_304_does_not_update_dom` 改为：若 DOM 变化则必须存在 200 响应，避免把 200 导致的正常更新误判为 304 错误。

## 分支状态

- Feature 分支：`feat-008-redis-adjust`（已 merge 到 develop）
- Tag：`v0.1.0-008-redis-adjust`
- Develop 分支：ahead of origin/develop by 1 commit

## 最后更新

2026-06-12

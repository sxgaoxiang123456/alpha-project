# Feature 002-data-failover · 最终归档报告

**Feature**: 002-data-failover（数据多源容灾）
**Status**: 已完成并归档
**完成日期**: 2026-06-03
**Tag**: `v0.1.0-data-failover`

---

## 交付清单

| 类别 | 内容 | 状态 |
|------|------|------|
| 数据模型 | CacheEntry（缓存持久化）+ DataSourceStatus（熔断器状态持久化） | ✅ |
| 核心基础设施 | CircuitBreaker（Closed/Open/Half-Open 状态机）+ CacheService（SQLite 缓存读写/过期/清理） | ✅ |
| 数据源适配器 | AkShareDataSource（主源）+ BaoStockDataSource（备源），统一异常映射 | ✅ |
| Facade 门面层 | DataSourceFacade.fetch_realtime() — 调用方零感知切换/降级/缓存 | ✅ |
| 健康检查 | HealthChecker + APScheduler 每 5 分钟探测，自动恢复主源 | ✅ |
| 可观测性 API | GET /system/data-sources — 返回各源健康状态 + 当前活跃源 | ✅ |
| 切换日志 | Facade 全路径结构化日志（主源成功/降级备源/缓存回退/全部不可用） | ✅ |
| 测试套件 | 203 passed, 0 failed（157 单元 + 7 集成 + 35 F1 legacy + 4 代码审查修复） | ✅ |
| 文档 | spec.md / plan.md / tasks.md / state.md / session.md | ✅ |

---

## 技术决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 熔断器状态持久化 | SQLite `data_source_status` 表 | 进程重启后状态不丢失，无需 Redis |
| 缓存持久化 | SQLite `cache_entries` 表 | 与自选股管理共享数据库，零额外依赖 |
| datetime 策略 | naive UTC (`datetime.utcnow()`) | SQLite 不支持 offset-aware，统一 naive 避免比较错误 |
| 外部库隔离 | 延迟导入（方法内部 `import akshare`/`import baostock`） | 测试环境无需安装外部库，通过 `patch.object` 实例方法隔离 |
| 探测恢复 | Open → Half-Open（1次成功）→ 连续2次成功 → Closed | 避免抖动，与 FR-008 对齐 |

---

## 已知限制（MVP 约束）

1. **超时配置未生效**：`config.py` 中 `data_source_timeout` / `data_source_retry` 声明但未实际使用（AkShare/BaoStock API 未暴露 timeout 参数）
2. **BaoStock 无实时接口**：当前使用 `query_history_k_data_plus`（5分钟 K 线）作为备用，非真正实时行情
3. **缓存清理频率**：每小时清理一次过期条目，非按需清理
4. **切换通知推送**：FR-010 交易时段推送通知尚未实现（依赖 F5 推送通道）
5. **单进程锁**：熔断器状态依赖 SQLite 行级锁，多进程/多实例场景需升级为分布式锁

---

## Git 归档

```
develop: f0dce01 merge: worktree-feat-002-data-failover → develop
tag:   v0.1.0-data-failover
```

---

## 规格冻结声明

`specs/002-data-failover/` 目录已冻结归档，永不删除。
后续需求变更请开新编号（003+）。

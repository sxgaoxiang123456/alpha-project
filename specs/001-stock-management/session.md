# Feature 001-stock-management · 最终归档报告

**Feature**: 001-stock-management（自选股管理）
**Status**: 已完成并归档
**完成日期**: 2026-06-03
**Tag**: `v0.1.0-stock-management`

---

## 交付清单

| 类别 | 内容 | 状态 |
|------|------|------|
| 后端 API | FastAPI + SQLAlchemy 2.0，股票搜索（AkShare/BaoStock 双源降级）、自选股 CRUD、CSV 导入导出、分组管理 | ✅ |
| 前端界面 | Jinja2 + Tailwind CSS + Material Symbols，自选股列表页、分组筛选、批量操作、空状态引导 | ✅ |
| 测试套件 | 124 passed, 0 failed（67 单元 + 41 集成 + 16 注入） | ✅ |
| 结构性补测 | C1 并发竞态 + C2 CSV 公式注入（backend-testing skill） | ✅ |
| 文档 | spec.md / plan.md / tasks.md / state.md / session.md | ✅ |

---

## 技术决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 数据库 | SQLite（MVP）→ PostgreSQL（v1.1） | 零配置、SQLAlchemy 抽象层可无缝迁移 |
| 前端 | Jinja2 SSR + Tailwind CDN | 无需构建工具链，设计参考可直接落地 |
| 并发锁 | `threading.Lock()` | 单进程 MVP 足够；多进程需升级分布式锁（见 R-PLAN-07） |
| CSV 安全 | 双向净化 `=+-@` | 阻止 Excel/Google Sheets/WPS 公式执行 |

---

## 已知限制（MVP 约束）

1. **并发锁**：`threading.Lock()` 仅单进程有效，多进程/多实例部署需升级为 Redis `SET NX` 或 PostgreSQL advisory lock
2. **async DB**：当前使用同步 SQLAlchemy，v1.1 可迁移至 `SQLAlchemy AsyncSession`
3. **名称搜索**：BaoStock 不支持名称模糊搜索，仅 AkShare 提供
4. **Modal**：编辑弹窗使用原生 JS prompt，v1.1 可替换为自定义 modal 组件

---

## Git 归档

```
main: 87c7d33 merge: develop → main (C1/C2 结构性缺口补测)
tag:  v0.1.0-stock-management
```

---

## 规格冻结声明

`specs/001-stock-management/` 目录已冻结归档，永不删除。
后续需求变更请开新编号（002+）。

# 实施进度 · 自选股管理

## 状态
**已完成并归档** — 2026-06-03

## 已完成
- [x] T01-T26 全部完成
- [x] Step 4 · 代码审查（两轮，所有 Critical 已修复）
- [x] Step 5 · 收尾（merge to main / tag / session.md）
- [x] C1 并发竞态补测（P0）— `threading.Lock()` + `IntegrityError` 捕获
- [x] C2 CSV 公式注入补测（P0）— 导入/导出双向净化

## 代码审查记录
- 第一轮审查：发现 D1/D3/D4 + R4，已修复并提交
- 第二轮审查：发现 C1/C2/C3 + I1-I6 + M1-M5
  - C1: tasks.md 勾选完成 ✓
  - C2: tests/conftest.py 补齐 ✓
  - C3: 移除冗余 validator ✓
  - M2: top_nav placeholder 中文化 ✓
  - I5: reviewer 误报（db.commit() 已在循环外），无需修复
  - I1/I2/I3/I4/I6: 已知 MVP 限制，记录于评审反馈

## 结构性缺口补测（backend-testing）
| 缺口 | 风险 | 状态 | 修复方式 |
|------|------|------|----------|
| C1 并发竞态 | P0 | 已闭合 | `threading.Lock()` 串行化 count+INSERT；`IntegrityError` 捕获返回 409 |
| C2 CSV 公式注入 | P0 | 已闭合 | 导入/导出双向净化 `=+-@` 公式触发字符，前缀单引号 |

## 测试状态
- 单元测试：67 passed
- 集成测试：41 passed（新增 2 个并发测试）
- CSV 注入测试：16 passed
- **总计：124 passed, 0 failed**

## Git 状态
- 分支 `001-stock-management` 已合并至 `main`（--no-ff）
- 分支 `develop` 已合并至 `main`
- Tag: `v0.1.0-stock-management`（指向含 C1/C2 补测的 merge commit）
- 远程推送：已完成

## 发布门批注
- **R-PLAN-07**：`threading.Lock()` 仅对单进程生效。多进程/多实例部署需升级为分布式锁（Redis `SET NX` 或 PostgreSQL advisory lock）。见 `plan.md` §Risk Register。

## 归档声明
本 feature 需求已冻结。specs/001-stock-management/ 目录永不删除。后续需求变更请开新编号（002+）。

## 最后更新
2026-06-03

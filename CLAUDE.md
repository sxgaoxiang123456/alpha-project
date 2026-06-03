# A股自动盯盘AI助手 · Claude 协作规范

## 1. 项目 WHAT

一款可私有部署的 A 股盯盘助手，聚焦「自选股管理 + 分钟级行情监控 + 价格/涨跌幅预警 + 推送通知」，替代手工刷新行情和手动设预警。MVP 包含 F1-F6 六大功能。见 `specs/prd.md` §2.2 / §5.1。

## 2. 项目 WHY

为无法实时盯盘的上班族散户降低信息焦虑——通过主动推送替代被动刷新，验证「低密度信息+主动推送」模式能否改善信息过载。见 `specs/prd.md` §2.2 学习目标 / §3.1 主要画像。

## 3. 工作流 HOW

**① 启动 feature**：读取 `specs/XXX-{feature}/spec.md` + `plan.md` + `tasks.md`，按 Phase 顺序执行

**② Task 启动必读**：`@specs/XXX-{feature}/spec.md`（需求）、`@specs/XXX-{feature}/plan.md`（架构）、`@specs/XXX-{feature}/tasks.md`（当前 task）；FE 任务额外读 `@design-reference/DESIGN.md` + `@design-reference/stitch-export/{page}/code.html`

**③ 测试纪律**：`superpowers:test-driven-development` — 先写测试（FAIL），再实现（PASS），最后重构

**④ Feature 完成**：`pytest tests/` 全量通过 → 更新 `tasks.md` 勾选完成项 → `git commit` 标注 `[BE]`/`[FE]`/`[INT]`

**⑤ 节奏铁律**：单 task 产出 1-3 个文件；每 Phase 结束后做 Checkpoint 验证；不跨 Phase 提前实现

## 4. 技术栈

> 项目处于设计阶段，`package.json` 尚未创建。以下从 `tasks.md` / `plan.md` 提取。

| 层级 | 技术 | 版本 | 来源 |
|:---|:---|:---|:---|
| 后端框架 | FastAPI | 未指定 | `001/tasks.md` T1 |
| ORM | SQLAlchemy | 2.0 | `001/tasks.md` T2 |
| 数据校验 | Pydantic | 未指定 | `001/tasks.md` T6 |
| 数据源 | AkShare / BaoStock | 未指定 | `prd.md` §12.1 |
| 模板引擎 | Jinja2 | 未指定 | `001/tasks.md` T15 |
| 样式框架 | Tailwind CSS | CDN | `001/tasks.md` T15 |
| 测试框架 | pytest / httpx | 未指定 | `001/tasks.md` T1 |
| 数据库 | PostgreSQL / Redis / ClickHouse | 未指定 | `06-架构基线决策.md` §1.1 |
| 部署 | Docker Compose / Nginx | 未指定 | `06-架构基线决策.md` §1.1 |

## 5. 命令清单

> `package.json` 不存在，暂无 npm scripts。以下从 `tasks.md` 提取。

| 命令 | 作用 | 来源 |
|:---|:---|:---|
| `uvicorn app.main:app` | 启动 FastAPI 服务 | `001/tasks.md` T2 |
| `docker build -t stock-mgt .` | 构建 Docker 镜像 | `001/tasks.md` T1 |
| `pytest tests/unit/` | 运行单元测试 | `001/tasks.md` T24 |
| `pytest tests/integration/` | 运行集成测试 | `001/tasks.md` T25 |

## 6. 项目宪法

所有实现决策的不可违反原则见 `@.specify/memory/constitution.md`。核心约束：信息展示边界（绝不交易）、单用户架构、零成本数据源优先、年运营成本 <= 1000 元。

## 7. 视觉规范

- 视觉 token 唯一来源：`@design-reference/DESIGN.md`
- 页面布局/组件组合参考：`@design-reference/stitch-export/{page}/code.html` + `screen.png`
- 关键约束：涨红跌绿、暗色模式唯一、中文界面、1280px 桌面固定网格

## 8. Anti-Patterns

1. **不要实现交易功能** — 合规红线，任何涉及下单/撮合的代码都不可接受
2. **不要预留多用户接口** — MVP 单用户假设，不要为权限系统留扩展点
3. **不要为亮色模式维护第二套 token** — 暗色模式是唯一主题
4. **不要硬编码色值/字号/间距** — 必须使用 DESIGN.md 的 design tokens
5. **不要违反 A 股红涨绿跌惯例** — 优先于任何国际化组件库默认配色
6. **不要为移动端做响应式适配** — MVP 仅支持 1280px+ 桌面端
7. **不要在代码中使用英文 UI 文案** — 所有用户-facing 文字必须是中文
8. **不要提前引入付费数据源** — 零成本方案验证失败前不升级

## 9. Behavioral Guidelines (Karpathy-Inspired)

以下 4 条原则适用于全项目所有 task 实现期，目的是减少 AI 编码的常见失误。

### 1. Think Before Coding

"Don't assume. Don't hide confusion. Surface tradeoffs."

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity First

"Minimum code that solves the problem. Nothing speculative."

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical Changes

"Touch only what you must. Clean up only your own mess."

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

### 4. Goal-Driven Execution

"Define success criteria. Loop until verified."

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

## 10. 关键文件导航

| 文件 | 何时读 | 内容 |
|:---|:---|:---|
| `specs/prd.md` | 项目启动、需求模糊时 | 业务 WHAT/WHY/非目标、用户故事、功能范围 |
| `specs/research/06-架构基线决策.md` | 技术选型、方案对比时 | 15 个项目调研、复用矩阵、改造成本 |
| `.specify/memory/constitution.md` | 任何实现决策前 | 不可违反原则、合规红线 |
| `design-reference/DESIGN.md` | FE 任务启动时 | 视觉 token、颜色、字号、间距规范 |
| `design-reference/stitch-export/{page}/code.html` | FE 组件实现时 | 高保真页面原型、组件组合方式 |
| `specs/001-stock-management/{spec,plan,tasks}.md` | F1 开发时 | 自选股 CRUD、分组、CSV 导入导出 |
| `specs/002-data-failover/{spec,plan,tasks}.md` | F2 开发时 | 多源容灾、自动切换 |
| `specs/003-realtime-quotes/{spec,plan,tasks}.md` | F3 开发时 | 实时行情、APScheduler |
| `specs/004-price-alert/{spec,plan,tasks}.md` | F4 开发时 | 预警规则、检测引擎、冷却期 |
| `specs/005-push-notification/{spec,plan,tasks}.md` | F5 开发时 | 飞书/Telegram 推送、双通道冗余 |
| `specs/006-dashboard/{spec,plan,tasks}.md` | F6 开发时 | Dashboard、设置页、前端组件 |
| `.specify/templates/{spec,plan,tasks}-template.md` | 新建 feature 时 | 标准化文档模板 |

## 11. LEARNINGS 自动加载

`@LEARNINGS.md`

每次会话开始，先吸收教训沉淀。实现新 feature 时若命中相关 type / 应用范围，主动避坑并明示 "本次绕开 LEARNINGS 第 N 条"。

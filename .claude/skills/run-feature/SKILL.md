---
name: run-feature
description: 对采用 spec-kit 式工作流的项目，实现/推进**单个**已就绪 feature（默认 specs/<id>-<name>/，含 spec+plan+tasks）的端到端标准流程。当用户说"实现 001 / 开发某个 feature / 跑 feature / 按这个流程做 X / run-feature / 继续下一个 feature / 把 <feature> 做了"等，或要对某个已就绪 feature 开工编码时，必须调用本 skill。它封装一套 opinionated 流程：worktree 隔离 → 读项目自身的 constitution/约定 → 按 tasks.md 走 TDD(RED→GREEN→REFACTOR) → 按任务标签([BE]/[FE]/[INT] 等)分流 → 多类缺陷 code review → 收尾 merge/tag；一次只跑一个 feature、跑完停下等审。区别于通用的 speckit-implement / superpowers:executing-plans——后两者是泛用执行器，本 skill 多了 worktree 隔离、读项目宪法合规、结构化缺陷审查清单、串行节奏控制。**项目特定的规则（技术栈、宪法条款、设计系统、里程碑命名）一律不写死，由项目自身的约定文件提供，skill 运行时去读、没有就跳过。** 不要用于：项目脚手架/基础设施初始化本身、撰写 spec/plan/tasks、跨多个 feature 并发。

---

# run-feature · 单 feature 实现标准流程（通用）

被调用时，实现**一个** feature（默认约定目录 `specs/<id>-<name>/`，含 spec/plan/tasks）。
目标 feature 来自调用参数（如 `/run-feature 001` 或 `/run-feature 003-push-channels`）。
**一次只跑一个 feature**，跑完停下等用户审。

> 本 skill 只规定**流程骨架**。所有项目特定的值——技术栈、宪法/原则条款、设计系统、初始化阶段叫什么——都**从项目自身的文件里读**，不在此写死。下面凡标「若有」的，项目没有就跳过该步。

## Step 0 · 前置自检（不满足就停下来问，别硬跑）

- **基础设施就绪**：项目的依赖/构建文件存在且测试框架能跑（按项目技术栈，如 `package.json` / `pyproject.toml` / `go.mod` / `Cargo.toml` 等）。
  若尚未初始化，先完成项目的初始化阶段（**无论它叫 M1 / Phase 0 / bootstrap / setup**），**不要**套本流程。
- **上游依赖就绪**：目标 feature 依赖的其他 feature 已完成（见该 feature 的进度记录与 spec 的依赖章节）。

## Step 1 · Worktree 隔离

```
claude --worktree feat-<id>-<feature>
```

**分支策略**：
- 主仓库保留在 `develop`（开发主干），不切换
- worktree 内**新建 feature 分支**（如 `feat-005-push-notification`），基于 `develop`
- 禁止 worktree 直接 checkout `develop`（git 不允许同一分支被多个 worktree 占用）

若项目用 `.worktreeinclude`（或等价机制）声明了要带进 worktree 的本地凭据/环境文件，会自动复制；没有则忽略。

## Step 2 · 启动四件事

① **读项目宪法/约定**（若有，常见路径 `.specify/memory/constitution.md`）：通读并遵守其**全部**原则——这些是项目不可违反的底线（视觉、业务、命名等）。本 skill 不预设条款编号或内容。
② 打开 `specs/<id>-<feature>/tasks.md`，取最小依赖且未完成的 task。
③ 每个 task 用 `superpowers:test-driven-development`（RED → GREEN → REFACTOR）。
④ 每个 task 跑完：更新项目的进度记录（若有，如 `state.md`）→ commit → **自动继续下一个 task**；全部 task 绿后才 STOP，等用户审。

## Step 3 · 按任务标签执行

tasks.md 中每个 task 的标签决定打法。常见标签 `[BE]` 后端 / `[FE]` 前端 / `[INT]` 集成；项目用别的标签体系就按其约定映射。

**[FE]（前端）**
- 写测试前先读**项目的设计系统/视觉约定**（若有，如 `DESIGN.md` + 设计参考样本目录），以及该 feature plan 中的视觉对齐章节（若有）。
- 用**项目指定的组件库/技术**实现；对照设计参考重建，不逐行照搬。
- 完成前逐项过**项目的前端规范 checklist**（若有）。

**[BE]（后端）**
- 按 plan 的契约规范写测试 stub（如 API 契约 OpenAPI / JSON Schema）；不涉及可忽略。
- 出参验证用 tasks.md 该 task 的「出参验证」列 + spec 的输入输出定义。

**[INT]（集成）** — 按子类型分流，**不要**一刀切"最后跑"：
- 基础设施类（config / migration / 跨 feature 契约 / 文档）：按 tasks.md 依赖图正常排序，**通常最先跑**，不依赖 [FE]/[BE]。
- E2E 类：本 feature 所有 [FE]/[BE] 通过后，最后跑真实链路（不 mock）。
- 跨 feature patch 类（改其他 feature 的源码）：改完**必须重跑被改 feature 的现有测试**，绿了才算过。

## Step 4 · 代码审查（Merge 前物理门禁）

**本 Step 是 merge 前的强制门禁，不可跳过。**

### 4.1 产出独立审查报告

调用 `superpowers:requesting-code-review` dispatch reviewer subagent，产出独立审查报告。

Reviewer 扫描至少覆盖：
① 韧性：缺重试 / 超时 / 熔断
② 横切一致性：鉴权 / 限流 / 日志 是否覆盖**所有**接口
③ 防御性：未处理 null / 缺输入校验 / 缺幂等键
④ DB 迁移（如涉及）：回滚脚本 + 分批操作
⑤ 项目宪法/设计系统合规（**仅当 feature 含 [FE] 且项目有设计系统时**）：是否硬编码了本应走 token 的视觉值、是否违反项目宪法里的视觉/业务铁律、是否引入了项目禁止的依赖

### 4.2 逐条评估（不可跳过）

等待 reviewer 返回完整报告后，**必须**调用 `superpowers:receiving-code-review` 逐条评估，产出评估表：

```
| 编号 | 类别 | 文件:行 | 描述 | 处置 | 理由 |
|:---|:---|:---|:---|:---|:---|
| 1 | Critical | foo.py:42 | ... | 接受修复 | ... |
| 2 | Important | bar.py:10 | ... | Push back | ... |
| 3 | Minor | baz.py:5 | ... | Deferred | ... |
```

处置列只允许三种值：**接受修复** / **Push back** / **Deferred**。

- **接受修复**：回对应 task 走 TDD 修复 → 重跑全量测试 → 重新 dispatch reviewer（重走 Step 4）
- **Push back**：在评估表中写明技术理由，不修复
- **Deferred**：记录到 `specs/<id>-<feature>/session.md`，不阻塞 merge

### 4.3 门禁条件（进入 Step 5 的前提）

**Critical / Important 缺陷必须处理完毕**，以下两种状态之一才允许进入 Step 5：
1. reviewer 报告 0 个 Critical + Important 缺陷（Minor 不影响 merge）
2. 所有 Critical / Important 缺陷都有明确处置决策（已修复 或 Push back），且不存在未修复的 Critical / Important 项

**Minor 缺陷不阻塞 merge**——可 Deferred 或 Push back，在 Step 5 报告中提醒用户即可。

**不满足门禁条件时，禁止进入 Step 5。**

## Step 5 · 收尾

**前置检查**：确认 Step 4 门禁已通过（Critical / Important 无未修复项）。未通过时返回 Step 4。

1. 最终 commit，message 含 `Closes <id>-<feature>`
2. **merge 回 develop 分支**（开发主干）
   - 在主仓库执行：`git checkout develop && git merge feat-<id>-<feature>`
   - merge 后删除本地 feature 分支：`git branch -d feat-<id>-<feature>`
   - **main 分支不直接接收 feature merge**（main 仅用于阶段性发布，通过 develop→main 的 PR/MR 合入）
3. 打 tag（如 `v0.1.0-<feature>`，按项目 tag 约定）
4. 更新该 feature 的会话/交接记录（若有，如 `session.md`）标记完成
5. 更新 `state.md` 标记全部完成（如尚未更新）
6. **feature 的 spec 目录永不删除**（CI 种子 + 下一 feature 的上下文）
7. 报告：本 feature 共 N task / M 个 [FE] / K 个 [BE]；审查发现 C 个 Critical + I 个 Important（已全部修复）+ M 个 Minor（已在报告中提醒用户）

> **与 `finishing-a-development-branch` 的职责边界**：run-feature Step 5 负责项目约定层面的收尾（commit/tag/state.md/session.md/spec 冻结）。若还需 Git 工作流层面的操作（push develop 到远程、创建 develop→main 的 PR/MR、清理 worktree），由 `finishing-a-development-branch` 补充执行。

## 节奏铁律

- 一个 feature 跑完**停下来等审**，再下一个。
- **严禁多 agent 并发**跑多个 feature（feature 间常有依赖拓扑）。

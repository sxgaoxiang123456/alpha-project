<!--
Sync Impact Report
- Version change: 0.1.0 → 0.2.0
- Added principles: XI. 界面语言统一为中文, XII. MVP 聚焦桌面端
- Modified principles: X. 暗色模式为默认且唯一模式（补充 MVP 不支持亮色切换的决策）
- Removed from Open Questions: 亮色模式支持、多语言切换策略、移动端优先顺序（均已决策并固化）
- Templates requiring updates:
  - ✅ plan-template.md: No outdated references found
  - ✅ spec-template.md: No outdated references found
  - ✅ tasks-template.md: No outdated references found
- Follow-up TODOs: Ratification date unknown (marked as TODO)
-->

# A股自动盯盘AI助手 Constitution

## Core Principles

### I. 信息展示边界（NON-NEGOTIABLE）

本产品定位为 A 股信息展示与预警工具，绝不提供下单、交易、撮合等任何实盘交易功能。所有简报、预警、行情展示输出必须标注"仅供参考，不构成投资建议"。

**Why**: 合规红线。PRD 第 2.3 节"非目标"明确排除实盘交易；PRD 第 7.4 节"合规"要求全程免责声明。逾越此边界将带来法律与监管风险。

### II. 单用户架构优先

MVP 阶段严格假设单用户部署与使用。所有功能设计、权限模型、数据隔离均以单用户为前提，不预留多用户并发或权限系统的扩展接口。

**Why**: PRD 第 5.4 节"Out-of-Scope"明确排除多用户权限；PRD 第 12.3 节"约束"列明"单用户架构，MVP 不支持多用户并发"。过早引入多用户会增加不必要的复杂度。

### III. 零成本数据源优先

数据层必须以零成本开源方案（AkShare + BaoStock）为第一选择。仅当 MVP 验证证明零成本方案无法满足稳定性要求时，才考虑升级至付费数据源。

**Why**: PRD 第 2.2 节"学习目标"要求验证零成本数据源能否支撑个人级盯盘需求；PRD 第 12.3 节"约束"列明年运营成本 <= 1000 元。数据源成本是项目可持续性的核心约束。

### IV. 推送即核心体验

预警推送不是附属功能，而是产品的核心交付通道。Dashboard 的被动浏览体验必须让位于主动推送的触达体验。推送通道（飞书主 + Telegram 备）的双通道冗余架构不可妥协。

**Why**: PRD 第 2 节背景指出目标用户是"无法实时盯盘的上班族散户"，产品价值在于"帮我盯"而非"给我看"。PRD 第 11.2 节"留存"指标要求 7 日活跃 > 60%，这依赖推送的打开率。

## Frontend Design System

### V. 视觉规范的唯一来源

所有前端视觉决策（颜色、字号、间距、圆角、阴影层级）的唯一权威来源是 `design-reference/DESIGN.md`。任何视觉实现必须使用 DESIGN.md 中定义的 design tokens，禁止在代码中硬编码任何色值、字号或间距值。

**Why**: DESIGN.md 是 Stitch 产出的设计系统全貌文档，包含了完整的 token 定义（colors, typography, spacing, rounded）。分散的硬编码会导致视觉不一致，且当设计系统更新时无法批量同步。

**执行依据**: `design-reference/DESIGN.md` 的 Colors、Typography、Layout & Spacing、Elevation & Depth、Shapes 各节。

### VI. 视觉参考样本的引用方式

当需要理解具体页面的布局结构、组件组合方式或交互细节时，应查阅 `design-reference/stitch-export/` 下对应的页面 HTML 文件。这些文件是视觉原型的可执行样本，用于回答"这个页面长什么样"的问题，而非"用什么色值"的问题。

**Why**: stitch-export 下的 HTML 文件（如 dashboard, alert_rules, watchlist）是 Stitch 产出的高保真视觉原型，展示了组件在实际页面中的组合方式、信息层级和响应式行为。但它们的 token 值必须与 DESIGN.md 对齐。

**执行依据**: `design-reference/stitch-export/` 目录下各页面的 `code.html` 与 `screen.png`。

### VII. A股市场惯例不可违反

涉及金融市场涨跌指示色的渲染，必须严格遵守 A 股市场惯例：涨为红色、跌为绿色。此约定优先于任何个人审美偏好或国际化组件库的默认配色。

**Why**: 目标用户是中国 A 股投资者，红涨绿跌是根深蒂固的市场认知。违反此惯例会导致用户混淆与信任丧失。PRD 第 2 节明确产品聚焦 A 股市场。

**执行依据**: `design-reference/DESIGN.md` 的"A-Share Semantic Standards"段落。

### VIII. 组件库基底：Tailwind CSS + shadcn/ui

前端组件必须以 Tailwind CSS 为样式框架，以 shadcn/ui 为组件基座。所有自定义组件应优先基于 shadcn/ui 的已有组件进行样式覆盖，而非从零实现。图标系统使用 Material Symbols Outlined。

**Why**: DESIGN.md 的"Checkboxes & Radios"段落明确提到"Follow shadcn/ui defaults"；所有 stitch-export 样本均使用 Tailwind CSS 的 utility classes 构建。这套组合能确保组件的可访问性、一致性和可维护性。

**执行依据**: `design-reference/DESIGN.md` 的 Components 章节；`design-reference/stitch-export/` 各页面的 `<script src="https://cdn.tailwindcss.com">` 与 Material Symbols Outlined 引用。

### IX. 信息密度哲学：低密度布局 + 高密度内容

页面布局遵循"低密度"原则——功能块之间保持 generous margins，确保结构层级清晰、视觉呼吸感充足。但内容块内部（尤其是数据表格）遵循"高密度"原则——严格行高、等宽数字、紧凑排版，最大化单屏可见信息量。

**Why**: DESIGN.md 的"Brand & Style"段落明确此产品面向"professional traders and quantitative analysts who require rapid data synthesis"，需要"High Density"的内容呈现来减少滚动和上下文切换，但"Low Density"的布局来避免认知疲劳。

**执行依据**: `design-reference/DESIGN.md` 的"Brand & Style"与"Layout & Spacing"段落。

### X. 暗色模式为默认且唯一模式

默认暗色模式是当前唯一需要支持的主题。MVP 阶段不支持亮色模式切换。所有视觉设计、组件样式、图表渲染必须以暗色模式为唯一目标进行设计、开发和验证，禁止为亮色模式预留或维护第二套 token。

**Why**: DESIGN.md 明确声明"Default Dark Mode"，且所有 stitch-export 样本的 `<html>` 标签均带有 `class="dark"`。暗色背景（deep navy-slate）是为长时间盯盘场景优化，减少眼部疲劳。MVP 阶段资源有限，支持双色模式会分散设计和开发精力。

**执行依据**: `design-reference/DESIGN.md` 的"Colors"段落；`design-reference/stitch-export/` 各页面的 `<html class="dark">`。

## Additional Constraints

### XI. 界面语言统一为中文

所有 UI 标签、按钮文案、导航项、提示信息、空状态文案必须使用中文。股票名称、代码、 ticker 等金融数据可保留原始语言形式，但用户-facing 的每一段文字必须是中文。

**Why**: 目标用户是中国 A 股个人投资者，中文是唯一需要支持的界面语言。MVP 阶段不做多语言切换，避免为 i18n 框架预留不必要的复杂度。stitch-export 样本中的英文 placeholder（如 "Search stock code..."）在实现时必须替换为中文。

**执行依据**: PRD 第 3 节"目标用户与画像"（中国散户）；`design-reference/stitch-export/` 各页面中导航标签的中文实践。

### XII. MVP 聚焦桌面端

MVP 阶段前端仅针对桌面端（1280px 及以上宽度）进行设计、开发和测试。布局使用固定宽度（1280px 居中）的桌面网格，不追求移动端的响应式适配或触摸交互优化。

**Why**: PRD 第 10.1 节 MVP 范围未包含 PWA 移动端（F12 列为 v1.2）。目标用户的主要使用场景是上班时的 PC 端（PRD 3.1 节"设备：PC"）。桌面端优先能最大化信息密度和表格展示效果，避免为移动端妥协核心体验。

**执行依据**: PRD 第 3.1 节目标用户画像（PC 为主）；PRD 第 5.3/10.4 节（PWA 列为 v1.2）；`design-reference/DESIGN.md` 的"Layout & Spacing"段落（1280px 固定网格）。

### XIII. 年运营成本上限

任何涉及外部服务、API、数据源的选型决策，必须以年运营成本 <= 1000 元人民币为硬约束。超出此预算的方案必须经过显式的成本效益论证并获得批准。

**Why**: PRD 第 12.3 节"约束"明确列明此预算上限。这是项目可持续性的经济基础。

## Governance

- 本 Constitution 优先于所有其他开发实践与临时决策。
- 新增或修改原则必须以 Pull Request 形式提交，附带修改理由与影响范围分析。
- 每次修改必须同步更新"Sync Impact Report"注释，记录版本变更、修改项与待办跟进。
- 开发过程中若发现 Constitution 与代码实现冲突，必须暂停实现并先修订 Constitution，禁止以代码迁就过时的原则。

## Implementation Discipline (for Superpowers handoff)

- Before executing any tasks.md, ALWAYS read .specify/memory/constitution.md FIRST.
- Always follow TDD: Red (failing test) → Green (minimum code) → Refactor.
- Always update tasks.md checkbox after EACH task completes.
- After each task: commit, then STOP and wait for "next".
- All [FE] tasks: MUST read root DESIGN.md and the matched
  design-reference/stitch-export/<page>/ BEFORE writing any component code.

**Version**: 0.2.0 | **Ratified**: TODO(RATIFICATION_DATE) | **Last Amended**: 2026-05-28

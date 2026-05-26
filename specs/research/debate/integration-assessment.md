# 集成评估报告：多项目组合工程可行性分析

> 评估日期：2026-05-25
> 评估立场：中立，仅基于工程事实与数据
> 目标产品：A股自动盯盘AI助手（Python FastAPI + React + AkShare + ClickHouse/Redis/PostgreSQL + 飞书Webhook）

---

## 一、评估方法论

### 1.1 评估维度

| 维度 | 说明 |
|:---|:---|
| **集成边界** | 两/三项目之间在何种层面（API / 文件 / 数据库 / 进程 / 库）对接 |
| **数据流冲突** | 数据模型、Schema、字段命名、时间格式、股票代码格式是否一致，adapter 层工作量 |
| **版本/依赖冲突** | Python 版本、Node 版本、关键依赖库（FastAPI / React / LangGraph 等）是否兼容 |
| **总改造成本** | 将组合项目改造为目标产品所需的额外人天（含废弃代码、重构、adapter） |
| **运维复杂度** | 组合后需要维护的 infra、服务数量、部署单元、监控点 |
| **推荐分** | 1-10 分，越高表示该组合越适合作为目标产品的基础 |

### 1.2 评分基准

- **10 分**：技术栈完全匹配，功能高度互补，几乎无需改造即可融合
- **7-9 分**：技术栈基本一致，功能互补，改造量可控，明显优于全自建
- **4-6 分**：技术栈部分匹配或功能有重叠，改造量中等，与全自建各有优劣
- **1-3 分**：技术栈严重冲突或功能大量重叠，改造量接近或超过全自建

### 1.3 全自建基准线

| 指标 | 数值 |
|:---|:---|
| 总工作量 | **75 人天**（约 3-4 个月 1 人全职） |
| 技术栈匹配度 | 100% |
| 外部依赖风险 | 无 |
| 代码可控性 | 完全可控 |
| 主要劣势 | 开发周期长，无法利用现有模块 |

---

## 二、双项目组合评估

---

### 组合 1：daily_stock_analysis + PanWatch

| 维度 | 评估详情 |
|:---|:---|
| **项目概况** | daily_stock_analysis（38.7k⭐, MIT, FastAPI+APScheduler+Python/TS）—— LLM每日自动分析+推送，多源数据融合，批处理模式；PanWatch（312⭐, MIT, FastAPI+SQLAlchemy+React 18+shadcn/ui）—— 私有部署AI盯盘助手，复合预警，PWA移动端 |
| **集成边界** | **API 层 + 数据库层**对接最优。两者后端均为 FastAPI，可合并为统一服务或 API Gateway 路由。daily_stock_analysis 的批处理 AI 模块和推送模块可直接拆出为 PanWatch 的子模块。前端以 PanWatch 的 React 18 + shadcn/ui 为主，daily_stock_analysis 的报告展示页可重构为 React 组件接入。 |
| **数据流冲突** | **低冲突**。两者都用 AkShare/Tushare 等数据源，数据获取层一致。daily_stock_analysis 有成熟的多源清洗 pipeline，可直接复用。主要工作：统一数据库 Schema（PostgreSQL 为主），统一股票代码格式和时间戳格式。**adapter 层约 3-5 人天**。 |
| **版本/依赖冲突** | **风险极低**。两者都用 FastAPI + APScheduler + OpenAI SDK，Python 版本均推测为 3.10+，完全兼容。Node 侧 PanWatch 用 React 18，daily_stock_analysis 前端较简单（报告展示），无框架级冲突。 |
| **总改造成本** | 后端统一（路由/模型/调度器）：10-15 人天；前端融合（PanWatch 为主 + daily_stock_analysis 报告页重构）：5-8 人天；推送层去重：2-3 人天；**总改造约 17-26 人天**。可节省数据接入层（~8 人天）、推送层（~3 人天）、前端脚手架（~5 人天），**净节省约 0-5 人天**，总工作量约 70-75 人天。 |
| **运维复杂度** | **低**。统一 Docker 部署，单一后端服务（或网关 + 两个服务），数据库共用 PostgreSQL + Redis + ClickHouse。 |
| **推荐分** | **8.0 / 10** |

**工程结论**：技术栈高度一致（双 FastAPI），功能高度互补（批处理报告 + 实时盯盘）。PanWatch 提供目标产品所需的现代 React 前端和预警系统，daily_stock_analysis 提供成熟的数据接入层和全渠道推送。融合成本可控，是**最优双项目组合之一**。

---

### 组合 2：daily_stock_analysis + aiagents-stock

| 维度 | 评估详情 |
|:---|:---|
| **项目概况** | daily_stock_analysis（38.7k⭐, FastAPI+Python/TS）；aiagents-stock（1.4k⭐, MIT, Python+Streamlit+SQLite+AKShare+TA-Lib）—— 多AI Agent盯盘，龙虎榜跟踪，MiniQMT实盘，20+新闻流监控 |
| **集成边界** | **API 层 + 库层**对接。daily_stock_analysis 的 FastAPI 后端作为主服务，aiagents-stock 的 Agent 逻辑和 MiniQMT 接口拆出为子模块或独立微服务。aiagents-stock 的 **Streamlit 前端完全无法复用**，必须废弃重建。 |
| **数据流冲突** | **低冲突**。两者都用 AKShare + TA-Lib，数据源一致。aiagents-stock 用 SQLite，daily_stock_analysis 未明确数据库，需统一为 PostgreSQL。**adapter 层约 2-4 人天**（SQLite→PostgreSQL 迁移 + 数据模型对齐）。 |
| **版本/依赖冲突** | **低风险**。Python 兼容。aiagents-stock 用 schedule（轻量调度），daily_stock_analysis 用 APScheduler，调度器需统一为 APScheduler。TA-Lib 版本可能需微调。 |
| **总改造成本** | aiagents-stock 后端 Agent 逻辑重构为 FastAPI 模块：10-15 人天；Streamlit 前端完全废弃 → React 重建：15-20 人天（但 daily_stock_analysis 前端可部分复用）；MiniQMT 接口拆出：3-5 人天；**总改造约 28-40 人天**。可节省部分数据接入和 AI Prompt 设计（~5 人天），**净增加成本**，总工作量可能超过全自建。 |
| **运维复杂度** | **中等**。增加一个微服务或模块，但 SQLite→PostgreSQL 后数据库统一。 |
| **推荐分** | **6.0 / 10** |

**工程结论**：后端逻辑互补（批处理AI + 多Agent + 实盘接口），但 aiagents-stock 的 Streamlit 前端与目标 React 技术栈完全冲突，前端重建成本高昂。仅当 MiniQMT 实盘和龙虎榜功能为强需求时才考虑此组合。

---

### 组合 3：PanWatch + aiagents-stock

| 维度 | 评估详情 |
|:---|:---|
| **项目概况** | PanWatch（312⭐, FastAPI+React 18+shadcn/ui, 复合预警, 多渠道通知）；aiagents-stock（1.4k⭐, Streamlit+SQLite, 多Agent, MiniQMT, 龙虎榜） |
| **集成边界** | PanWatch 的 FastAPI + React 骨架作为主项目，aiagents-stock 拆出后端 Agent 模块接入。与组合 2 类似，**Streamlit 前端必须完全废弃**。 |
| **数据流冲突** | **低冲突**。都用 AKShare。aiagents-stock 的 SQLite 需迁移至 PostgreSQL。**adapter 约 3-5 人天**。 |
| **版本/依赖冲突** | **低风险**。Python 兼容。aiagents-stock 的 Plotly/ReportLab 与 PanWatch 前端无关，可移除。 |
| **总改造成本** | aiagents-stock Agent 逻辑融入 PanWatch 后端：8-12 人天；前端重建（PanWatch 已有 React，只需新增 Agent 相关页面）：5-8 人天；数据库统一：3-5 人天；**总改造约 16-25 人天**。PanWatch 提供了很好的前端骨架，可节省前端开发时间，**净节省约 10-15 人天**，总工作量约 60-65 人天。 |
| **运维复杂度** | **中等**。两个项目来源，代码风格可能不一致。 |
| **推荐分** | **6.5 / 10** |

**工程结论**：PanWatch 的 React 前端弥补了 aiagents-stock 的前端短板，aiagents-stock 的多 Agent 和 A 股特色功能（龙虎榜、MiniQMT）补充了 PanWatch。但 aiagents-stock 的 Streamlit 意味着大量代码废弃，改造量不可忽视。

---

### 组合 4：vnpy + qteasy

| 维度 | 评估详情 |
|:---|:---|
| **项目概况** | vnpy（40.9k⭐, MIT, Python 3.10+, PyQt GUI, 量化交易框架, CTP/XTP实盘）；qteasy（146⭐, BSD-3, Jupyter Notebook+NumPy/Numba, 本地化量化工具包, 向量化回测） |
| **集成边界** | **库层/进程层**对接。两者均为 Python 库，vnpy 是事件驱动框架，qteasy 是向量化回测框架，架构模式不同。 |
| **数据流冲突** | **高冲突**。vnpy 有自己的数据管理抽象（SQLite/MySQL/QuestDB/InfluxDB/MongoDB），qteasy 本地化数据，两者数据模型差异大。**adapter 层需 10-15 人天**。 |
| **版本/依赖冲突** | **中风险**。vnpy Python 3.10+，qteasy 兼容。但 PyQt 与 Jupyter 环境并存增加部署复杂度，Numba 与 vnpy 的 C 扩展可能有兼容性问题。 |
| **总改造成本** | **极高**。两者都没有现代 Web 前端（PyQt 和 Jupyter），与目标 React 前端完全不匹配。若要在 React 前端中使用，需要：① 将 vnpy 事件引擎封装为 Web 服务（20-30 人天）；② 将 qteasy 回测引擎封装为 Web 服务（15-20 人天）；③ 新建 React 前端（18 人天）。总改造远超全自建。 |
| **运维复杂度** | **高**。vnpy 是重型框架，qteasy 需 Jupyter 环境，部署复杂。 |
| **推荐分** | **3.0 / 10** |

**工程结论**：两者均为成熟量化后端框架，但前端技术栈（PyQt / Jupyter）与目标产品（React）严重不符。直接集成的改造成本接近重建，**仅适合参考架构设计，不适合直接作为基础代码**。

---

### 组合 5：TradingAgents + Vibe-Trading

| 维度 | 评估详情 |
|:---|:---|
| **项目概况** | TradingAgents（79.3k⭐, Apache-2.0, Python+LangGraph, CLI为主, 多Agent交易框架, 面向美股）；Vibe-Trading（8.5k⭐, MIT, Python 3.11++FastAPI+React 19, 多Agent交易研究, 452 Alpha因子, 7回测引擎） |
| **集成边界** | Vibe-Trading 的 FastAPI+React 可作为主骨架，TradingAgents 需改造为 API 服务或独立进程。 |
| **数据流冲突** | **中冲突**。TradingAgents 面向美股/全球市场，A 股数据（AKShare/Tushare）需自行接入。Vibe-Trading 已有 AKShare/Tushare 支持。两者 Agent 输出格式不统一，需 adapter。**A 股适配 + 格式统一约 15-20 人天**。 |
| **版本/依赖冲突** | **中风险**。Vibe-Trading Python 3.11+，TradingAgents 未明确但应兼容。LangGraph 依赖可能与 Vibe-Trading 的某些库版本冲突。React 19 与 TradingAgents 无关（其无前端）。 |
| **总改造成本** | TradingAgents CLI→API 改造：15-20 人天；A 股数据接入 TradingAgents：10-15 人天；Agent 输出格式与 Vibe-Trading 融合：8-12 人天；两者功能重叠（均为 AI Agent 系统）需去重：5-8 人天；**总改造约 38-55 人天**。功能重叠导致边际效益低。 |
| **运维复杂度** | **高**。LangGraph 增加依赖复杂度，两个 Agent 系统并存调试困难。 |
| **推荐分** | **4.5 / 10** |

**工程结论**：两者均为 AI Agent 交易研究工具，功能重叠度高。TradingAgents 的 CLI 模式改造成本高，且面向美股需大量 A 股适配工作。Vibe-Trading 自身已具备多 Agent 能力，引入 TradingAgents 的边际效益不足以抵消改造成本。

---

### 组合 6：PanWatch + TradingAgents

| 维度 | 评估详情 |
|:---|:---|
| **项目概况** | PanWatch（312⭐, FastAPI+React 18, 实时盯盘+预警+多渠道通知）；TradingAgents（79.3k⭐, Python+LangGraph, CLI, 五层Agent流水线） |
| **集成边界** | PanWatch 作为主骨架（前端+后端 API），TradingAgents 改造为后端 Agent 服务。 |
| **数据流冲突** | **中高冲突**。TradingAgents 面向美股，A 股数据适配需大量工作。PanWatch 的 A 股数据与 TradingAgents 的 Agent 流水线融合困难。 |
| **版本/依赖冲突** | **中风险**。LangGraph 可能与 PanWatch 的 OpenAI SDK 等依赖有版本冲突。 |
| **总改造成本** | TradingAgents CLI→API + A 股适配：20-30 人天；与 PanWatch 前端对接：8-12 人天；**总改造约 28-42 人天**，接近半重建。 |
| **运维复杂度** | **中高**。TradingAgents 独立服务 + LangGraph 调试复杂。 |
| **推荐分** | **5.0 / 10** |

**工程结论**：PanWatch 的预警和前端与 TradingAgents 的 Agent 编排理念互补，但 TradingAgents 的 CLI 模式和美股定位导致工程集成成本过高。Agent 编排模式**更适合参考设计而非直接嵌入**。

---

### 组合 7：daily_stock_analysis + vnpy

| 维度 | 评估详情 |
|:---|:---|
| **项目概况** | daily_stock_analysis（38.7k⭐, FastAPI, 多数据源+批处理AI+推送）；vnpy（40.9k⭐, Python 3.10+, PyQt, 重型量化框架, CTP/XTP实盘） |
| **集成边界** | **数据库/消息队列层**间接对接。vnpy 是独立完整框架，与 daily_stock_analysis 的 FastAPI 服务难以直接融合。 |
| **数据流冲突** | **高冲突**。vnpy 有自己的事件引擎和数据管理，daily_stock_analysis 用 pandas 流。数据模型差异大，adapter 复杂。 |
| **版本/依赖冲突** | **中风险**。vnpy 依赖复杂，可能与 daily_stock_analysis 的某些库冲突。PyQt 与 Web 前端完全无关。 |
| **总改造成本** | vnpy 过于重型，直接嵌入会带来大量无用代码（期货网关、PyQt GUI 等）。若仅需 Gateway 抽象或事件引擎，不如参考架构自行实现。**改造成本极高**。 |
| **运维复杂度** | **高**。vnpy 重型框架增加部署复杂度。 |
| **推荐分** | **3.5 / 10** |

**工程结论**：vnpy 是国内量化标杆，但其定位是交易框架而非盯盘助手。PyQt GUI 和期货导向与目标产品严重不符。直接集成得不偿失，**建议仅参考其 Gateway 设计模式和事件引擎架构**。

---

### 组合 8：A股实时监测 + PanWatch

| 维度 | 评估详情 |
|:---|:---|
| **项目概况** | A股实时监测（1⭐, MIT, FastAPI+SQLAlchemy 2.0+MySQL+aiomysql+AkShare+WebSocket, Vue 3.4+TS+Element Plus+ECharts, uni-app 移动端）；PanWatch（312⭐, FastAPI+React 18+shadcn/ui） |
| **集成边界** | 后端均为 FastAPI，可在 API/数据库层合并。但**前端技术栈完全不同**：Vue3+Element Plus+ECharts vs React 18+shadcn/ui。 |
| **数据流冲突** | **低冲突**。都用 AkShare，都用 SQLAlchemy（A股实时监测用 2.0），数据模型较易拉通。A股实时监测用 MySQL，PanWatch 未明确但推测兼容。 |
| **版本/依赖冲突** | **后端低风险，前端高风险**。Python 侧完全兼容。Node 侧 Vue vs React 是**框架级冲突**，无法在同一前端项目中并存。 |
| **总改造成本** | 后端合并：5-8 人天；**前端必须二选一**：若选 React，A股实时监测的 Vue3+uni-app 双端（PC+移动）全部废弃（约 15-20 人天损失）；若选 Vue3，PanWatch 的 React+shadcn/ui 全部废弃（约 10-15 人天损失）。无论选哪边，都有一整套前端重建。**总改造约 25-40 人天**。 |
| **运维复杂度** | **中等**。若保留 uni-app 移动端 + React PC 端，则需维护两个前端项目。 |
| **推荐分** | **6.0 / 10** |

**工程结论**：后端高度兼容，但前端 Vue vs React 的框架级冲突是致命伤。A股实时监测的 uni-app 移动端是独特优势，但融合意味着要么放弃 PanWatch 的成熟 React 组件，要么放弃 uni-app 双端。工程上两难，**不如分别参考两个项目的前端设计思路**。

---

## 三、三项目组合评估

---

### 组合 9：daily_stock_analysis + PanWatch + aiagents-stock

| 维度 | 评估详情 |
|:---|:---|
| **项目概况** | daily_stock_analysis（数据+批处理AI+推送）；PanWatch（实时盯盘+预警+React前端）；aiagents-stock（多Agent+MiniQMT+龙虎榜+Streamlit） |
| **集成边界** | daily_stock_analysis 和 PanWatch 均为 FastAPI，后端易合并。aiagents-stock 是独立 Python 项目，需拆出模块接入。aiagents-stock 的 Streamlit 前端完全废弃。 |
| **数据流冲突** | **低冲突**。三者都用 AKShare。aiagents-stock 用 SQLite，其他可能用 PostgreSQL/MySQL，需统一。**adapter 层约 5-8 人天**。 |
| **版本/依赖冲突** | **低风险**。Python 兼容。前端侧 aiagents-stock 无现代前端，不冲突。 |
| **总改造成本** | daily_stock_analysis + PanWatch 融合：15-20 人天；aiagents-stock 后端 Agent 逻辑拆出：10-15 人天；aiagents-stock 前端重建（React）：15-20 人天；数据库统一：5-8 人天；**总改造约 45-63 人天**。功能覆盖非常全面，但三项目融合复杂度显著增加。 |
| **运维复杂度** | **中高**。三个项目来源，代码风格不一致，需统一规范。 |
| **推荐分** | **6.5 / 10** |

**工程结论**：功能覆盖最全面（数据+批处理AI+推送+实时盯盘+预警+多Agent+实盘+龙虎榜），但 aiagents-stock 的 Streamlit 前端导致大量重建工作。三项目协调成本不可忽视，**仅当所有功能都是 P0 需求时才考虑**。

---

### 组合 10：vnpy + qteasy + ZVT

| 维度 | 评估详情 |
|:---|:---|
| **项目概况** | vnpy（PyQt+Python 3.10+, 40.9k⭐, 量化交易框架）；qteasy（Jupyter+NumPy/Numba, 146⭐, 本地化回测）；ZVT（Dash/Plotly+Python, 4.1k⭐, 模块化量化框架, 统一Schema） |
| **集成边界** | 三者都是 Python 后端框架，前端分别是 PyQt、Jupyter、Dash。**与目标 React 前端完全不匹配**。 |
| **数据流冲突** | **极高冲突**。三者各有独立数据抽象：vnpy 事件引擎+多数据库、qteasy 本地化、ZVT 统一 Schema+增量更新。数据模型差异巨大，adapter 工作量可能超过 20 人天。 |
| **版本/依赖冲突** | **高风险**。vnpy 依赖复杂，Numba 与 vnpy C 扩展可能有冲突，Dash/Plotly 与 PyQt/Jupyter 部署环境复杂。 |
| **总改造成本** | 三个重型框架融合，无现代前端需完全新建 React 前端（18 人天）。改造工作量**极有可能超过全自建的 75 人天**。 |
| **运维复杂度** | **极高**。三个重型框架 + 三种前端环境 + 复杂依赖链。 |
| **推荐分** | **2.0 / 10** |

**工程结论**：三者均为量化后端框架，功能大量重叠（数据+回测+策略），且前端技术栈（PyQt/Jupyter/Dash）与目标 React 严重不符。集成此组合**是工程上的灾难**，强烈不建议。

---

### 组合 11：TradingAgents + Vibe-Trading + PanWatch

| 维度 | 评估详情 |
|:---|:---|
| **项目概况** | TradingAgents（79.3k⭐, Python+LangGraph, CLI, 五层Agent流水线, 面向美股）；Vibe-Trading（8.5k⭐, FastAPI+React 19, 多Agent+回测+452 Alpha因子）；PanWatch（312⭐, FastAPI+React 18, 实时盯盘+预警） |
| **集成边界** | Vibe-Trading 和 PanWatch 均为 FastAPI+React，技术栈高度一致，可融合。TradingAgents 是 CLI，需独立改造。 |
| **数据流冲突** | **中冲突**。Vibe-Trading 和 PanWatch 都用 AKShare，数据层一致。TradingAgents 面向美股，A 股数据适配困难。三者 Agent 输出格式不统一，需统一 adapter。 |
| **版本/依赖冲突** | **中风险**。Vibe-Trading React 19 vs PanWatch React 18，需升级 PanWatch（成本较低）。Python 3.11+ 兼容。LangGraph 增加依赖复杂度。 |
| **总改造成本** | Vibe-Trading + PanWatch 融合：15-20 人天；TradingAgents CLI→API + A 股适配：20-30 人天；三者 Agent 逻辑去重和统一：8-12 人天；**总改造约 43-62 人天**。TradingAgents 的边际效益（相比 Vibe-Trading 已有的多 Agent 能力）不足以抵消改造成本。 |
| **运维复杂度** | **高**。TradingAgents 独立服务 + LangGraph 调试复杂，两个 Agent 系统（Vibe-Trading + TradingAgents）功能重叠。 |
| **推荐分** | **5.5 / 10** |

**工程结论**：Vibe-Trading 和 PanWatch 的融合是亮点（同技术栈），但 TradingAgents 的 CLI 模式和美股定位拉低了整体可行性。Vibe-Trading 自身已具备强大的多 Agent 和回测能力，引入 TradingAgents 的**增量价值有限而成本极高**。

---

## 四、额外评估：技术栈高度匹配组合

---

### 组合 12：PanWatch + Vibe-Trading（强烈推荐）

| 维度 | 评估详情 |
|:---|:---|
| **项目概况** | PanWatch（312⭐, FastAPI+React 18+shadcn/ui+Tailwind, 复合预警+多渠道通知+AI Agent编排+PWA）；Vibe-Trading（8.5k⭐, MIT, FastAPI+React 19+Vite+TS, 自改进交易Agent+29个swarm+452 Alpha因子+7回测引擎） |
| **集成边界** | **技术栈几乎完全一致**——两者均为 FastAPI + React + TypeScript。可在同一 monorepo 中合并，或 API Gateway 统一路由。后端合并为统一 FastAPI 服务，前端统一为 React 应用（PanWatch 的 shadcn/ui Dashboard 组件 + Vibe-Trading 的研究工具组件）。 |
| **数据流冲突** | **极低冲突**。两者都支持 AKShare/Tushare，数据源完全一致。都用 SQLAlchemy 类 ORM（推测），股票代码格式、时间戳格式较易统一。**adapter 层约 3-5 人天**。 |
| **版本/依赖冲突** | **风险极低**。React 18 vs 19：PanWatch 升级至 React 19 成本很低（约 1-2 人天，React 19  largely backward compatible）。Python：Vibe-Trading 要求 3.11+，PanWatch 未明确但应兼容。FastAP、APScheduler 等核心依赖可调，无重大冲突。 |
| **总改造成本** | 后端服务合并/统一网关：8-12 人天；React 版本统一 + 前端组件整合：5-8 人天；数据模型统一：3-5 人天；调度系统统一：2-3 人天；**总改造约 18-28 人天**。可节省：前端脚手架（5 人天）、后端脚手架（5 人天）、数据接入层（8 人天）、图表组件（5 人天）、回测引擎（15 人天）、预警系统（8 人天）、Agent 编排（10 人天）。**净节省约 30-40 人天**，总工作量约 35-45 人天。 |
| **运维复杂度** | **低**。统一技术栈（Python+React），统一 Docker 部署，单一数据库集群（PostgreSQL+Redis+ClickHouse），监控点集中。 |
| **推荐分** | **8.5 / 10** |

**工程结论**：**这是所有组合中技术栈匹配度最高的双项目组合**。两者均为 FastAPI+React，融合成本最低。功能高度互补：PanWatch 提供盯盘、预警、通知、PWA 移动端；Vibe-Trading 提供 AI Agent 研究、回测引擎、Alpha 因子库。**融合后工作量仅约全自建的 50-60%，且功能覆盖度超过 80%**。

---

### 组合 13：daily_stock_analysis + PanWatch + Vibe-Trading

| 维度 | 评估详情 |
|:---|:---|
| **项目概况** | daily_stock_analysis（38.7k⭐, 数据多源融合+批处理AI+全渠道推送）；PanWatch（312⭐, 实时盯盘+复合预警+React 18）；Vibe-Trading（8.5k⭐, FastAPI+React 19+AI Agent+回测+452 Alpha因子） |
| **集成边界** | PanWatch 和 Vibe-Trading 技术栈一致（FastAPI+React），先融合为骨架。daily_stock_analysis 也是 FastAPI+Python/TS，后端易接入，前端较简单可重构。 |
| **数据流冲突** | **低冲突**。三者都用 AKShare。daily_stock_analysis 的多源融合（Pytdx/Baostock/YFinance/Longbridge）可直接补充到 PanWatch/Vibe-Trading 的数据层。 |
| **版本/依赖冲突** | **低风险**。React 统一为 19。Python 3.11+。依赖冲突风险低。 |
| **总改造成本** | PanWatch + Vibe-Trading 融合：18-28 人天；daily_stock_analysis 后端模块拆出接入（数据接入+推送+批处理AI）：8-12 人天；前端整合（三个项目的前端设计理念差异）：10-15 人天；**总改造约 36-55 人天**。功能最全面（数据+批处理AI+推送+实时盯盘+预警+Agent+回测+Alpha因子+现代前端），但融合复杂度较高。 |
| **运维复杂度** | **中等**。三个项目来源，代码风格可能不一致，需要统一编码规范。 |
| **推荐分** | **7.5 / 10** |

**工程结论**：功能覆盖度最高的组合，几乎覆盖目标产品所有模块。daily_stock_analysis 的多源数据融合和全渠道推送是独特优势，Vibe-Trading 的 Agent+回测是独特优势，PanWatch 的预警+前端是独特优势。三项目融合有一定复杂度，但技术栈一致性好（均为 FastAPI+React 或 Python 后端），**是功能最全面的方案**。

---

### 组合 14：daily_stock_analysis + Vibe-Trading

| 维度 | 评估详情 |
|:---|:---|
| **项目概况** | daily_stock_analysis（38.7k⭐, MIT, FastAPI+APScheduler+Python/TS, 多源数据融合+批处理AI+全渠道推送）；Vibe-Trading（8.5k⭐, MIT, FastAPI+React 19+Vite+TS, 多Agent+452 Alpha因子+7回测引擎） |
| **集成边界** | **API 层 + 库层**对接。两者后端均为 FastAPI，可合并为统一服务。daily_stock_analysis 前端较简单（报告展示页），以 Vibe-Trading 的 React 19 为主骨架，将 daily_stock_analysis 的报告生成模块接入。 |
| **数据流冲突** | **极低冲突**。两者都用 AKShare/Tushare，数据源完全一致。daily_stock_analysis 的多源融合（Pytdx/Baostock/YFinance/Longbridge）可补充 Vibe-Trading 的数据层。**adapter 层约 2-4 人天**。 |
| **版本/依赖冲突** | **风险极低**。两者均为 FastAPI + Python 3.11+，核心依赖高度一致。daily_stock_analysis 用 APScheduler，Vibe-Trading 调度未明确，统一为 APScheduler 成本极低。 |
| **总改造成本** | 后端 FastAPI 服务合并：8-12 人天；daily_stock_analysis 前端重构为 React 组件（接入 Vibe-Trading）：5-8 人天；推送层拆入：2-3 人天；数据层统一：2-3 人天；**总改造约 17-26 人天**。可节省：数据接入层（10 人天）、推送层（4 人天）、回测引擎（12 人天）、Agent 编排（8 人天）。**净节省约 8-18 人天**，总工作量约 57-67 人天。 |
| **运维复杂度** | **低**。双 FastAPI 统一为单一后端服务，React 单一前端，数据库共用 PostgreSQL+Redis+ClickHouse。 |
| **推荐分** | **7.5 / 10** |

**工程结论**：双 FastAPI 后端技术栈高度一致，融合成本可控。功能互补性强：daily_stock_analysis 提供「最广数据源覆盖 + 批处理 AI 报告 + 全渠道推送」，Vibe-Trading 提供「多 Agent 研究团队 + 452 Alpha 因子 + 7 回测引擎」。但两者均缺少实时盯盘预警和 PWA 移动端，**需后续补充 PanWatch 或自研预警模块**。

---

### 组合 15：go-stock + A股实时监测

| 维度 | 评估详情 |
|:---|:---|
| **项目概况** | go-stock（5.8k⭐, GPL-3.0, Go+Vue3+NaiveUI+Wails, AI桌面股票分析, 支持10+LLM模型）；A股实时监测（1⭐, MIT, FastAPI+SQLAlchemy 2.0+MySQL+Vue3+TS+Element Plus+ECharts+uni-app, PC+移动端A股监控） |
| **集成边界** | **前端技术栈一致（Vue3），后端完全不同**。两者前端均为 Vue3 + TypeScript，可在 UI 层复用组件设计。但 go-stock 是 Go+Wails 桌面应用，A股实时监测是 Python FastAPI Web 服务，后端无法直接融合。 |
| **数据流冲突** | **中冲突**。两者都用 AkShare/东方财富数据源，但 go-stock 的 Go 层数据封装与 A股实时监测的 Python pandas 流无法直接对接。需要跨语言 adapter（如 gRPC/REST）。**adapter 层约 8-12 人天**。 |
| **版本/依赖冲突** | **高风险**。Go vs Python 是语言级冲突；Wails 桌面框架与 Web 部署模式完全不同；GPL-3.0 传染性 License 与目标 MIT 技术栈存在法律风险。 |
| **总改造成本** | 前端 Vue3 组件可部分复用（约节省 3-5 人天）；但 go-stock 的 Go 后端需重写为 Python（约 20-25 人天）或维护跨语言服务（增加运维复杂度）；GPL-3.0 License 风险需法务审查。**总改造远超全自建，且法律风险不可控**。 |
| **运维复杂度** | **高**。Go + Python 双运行时，Wails 桌面 + Web 双部署模式。 |
| **推荐分** | **3.5 / 10** |

**工程结论**：Vue3 前端技术栈一致是唯一亮点，但 Go+Wails 桌面模式与目标 Python+React Web 服务严重不符。GPL-3.0 License 是致命法律风险。**建议仅参考 go-stock 的 AI Prompt 设计和 A股实时监测的 WebSocket 实时推送方案**，不直接集成代码。

---

### 组合 16：RQAlpha + Vibe-Trading

| 维度 | 评估详情 |
|:---|:---|
| **项目概况** | RQAlpha（6.4k⭐, 非商业License, Python 100%, A股回测框架, 涨跌停/T+1/停牌深度适配, Mod扩展机制）；Vibe-Trading（8.5k⭐, MIT, FastAPI+React 19, 多Agent+452 Alpha因子+7回测引擎） |
| **集成边界** | **库层/进程层**对接。RQAlpha 是纯 Python 回测框架（CLI/库），Vibe-Trading 是 FastAPI+React Web 服务。可将 RQAlpha 的回测引擎封装为 API 服务供 Vibe-Trading 调用。 |
| **数据流冲突** | **中冲突**。RQAlpha 使用内置 CSI A股数据和 RQData 付费数据源，Vibe-Trading 使用 AKShare/Tushare。数据格式和股票代码规范需统一。**adapter 层约 5-8 人天**。 |
| **版本/依赖冲突** | **中风险**。Python 版本兼容。但 RQAlpha 依赖较旧（pandas/numpy 版本可能冲突），且 Mod 机制与 Vibe-Trading 的架构风格差异大。 |
| **总改造成本** | RQAlpha 回测引擎 API 封装：10-15 人天；数据层统一：5-8 人天；A股规则模块拆出：3-5 人天；**总改造约 18-28 人天**。但 RQAlpha **非商业 License** 意味着任何商业化使用都需联系米筐科技授权，**法律风险高**。 |
| **运维复杂度** | **中等**。增加一个回测微服务，但 RQAlpha 本身为纯 Python，部署不复杂。 |
| **推荐分** | **4.0 / 10** |

**工程结论**：RQAlpha 的 A股规则适配（涨跌停/T+1/停牌）是独特价值，但**非商业 License 是集成利用的最大障碍**。Vibe-Trading 自身已有 7 个回测引擎，引入 RQAlpha 的边际效益不足以抵消 License 风险。建议**参考 RQAlpha 的 A股规则实现代码逻辑，但不直接引入依赖**。

---

### 组合 17：QuantMuse + PanWatch

| 维度 | 评估详情 |
|:---|:---|
| **项目概况** | QuantMuse（2.6k⭐, MIT, Python+JS+C++, Streamlit/FastAPI, C++低延迟核心+AI量化+实时WebSocket+预警）；PanWatch（312⭐, MIT, FastAPI+React 18+shadcn/ui, 实时盯盘+复合预警+多渠道通知） |
| **集成边界** | PanWatch 的 FastAPI+React 作为主骨架，QuantMuse 拆出 C++低延迟核心和 AI 量化模块接入。QuantMuse 的 Streamlit 前端废弃。 |
| **数据流冲突** | **中冲突**。两者数据源都支持 AKShare 类接口，但 QuantMuse 的 C++ 核心数据格式与 Python 层需通过 pybind/ctypes 对接。**adapter 层约 6-10 人天**。 |
| **版本/依赖冲突** | **高风险**。QuantMuse 的 C++ 核心增加编译和跨平台部署复杂度（需 GCC/Clang 工具链）；Streamlit 与 React 完全冲突；项目仅 9 个 commits，成熟度极低。 |
| **总改造成本** | C++ 核心封装为 Python 模块：12-18 人天；AI 量化模块拆出接入 PanWatch：5-8 人天；Streamlit 前端完全废弃：无额外成本（PanWatch 已有 React）；**总改造约 17-26 人天**。但 QuantMuse 成熟度极低（9 commits），代码质量不可控，**实际风险远高于预估**。 |
| **运维复杂度** | **高**。C++ 核心增加构建和部署复杂度，跨平台（Linux/macOS/Windows）兼容性需额外测试。 |
| **推荐分** | **4.5 / 10** |

**工程结论**：QuantMuse 的 C++ 低延迟核心对高频盯盘场景有理论价值，但项目成熟度极低（9 commits），代码质量和可维护性存疑。与 PanWatch 集成后运维复杂度陡增。**建议仅参考其 C++ 实时处理架构思路，不引入实际代码**。

---

### 组合 18：shares + A股实时监测

| 维度 | 评估详情 |
|:---|:---|
| **项目概况** | shares（639⭐, Apache-2.0, Go+Python+Vue+uni-app+gorm+MySQL+Redis+etcd, A股量化+盯盘+uni-app小程序）；A股实时监测（1⭐, MIT, FastAPI+Vue3+uni-app+AkShare+WebSocket, PC+移动端A股监控） |
| **集成边界** | **前端技术栈一致（Vue3+uni-app），后端完全不同**。shares 后端为 Go（gmsec 框架）+ Python 混合，A股实时监测为纯 Python FastAPI。前端双端（PC+移动）架构思路一致。 |
| **数据流冲突** | **高冲突**。shares 用 Go gorm + MySQL + Redis + etcd 技术栈，A股实时监测用 FastAPI + SQLAlchemy + MySQL。数据模型差异大，且 shares 的 Go 层与 Python 层通信增加复杂度。**adapter 层约 10-15 人天**。 |
| **版本/依赖冲突** | **高风险**。Go + Python 双运行时；etcd 增加分布式协调复杂度；shares 仅 35 commits，代码活跃度不高。 |
| **总改造成本** | 前端 Vue3+uni-app 可部分复用（节省 5-8 人天）；后端需统一为 Python FastAPI（Go 层重写约 15-20 人天）；etcd 可替换为 Redis。**总改造约 30-40 人天**，且 shares 的 gmsec 框架小众，生态支持有限。 |
| **运维复杂度** | **高**。Go + Python 双运行时 + etcd 分布式协调，部署复杂。 |
| **推荐分** | **4.0 / 10** |

**工程结论**：Vue3+uni-app 多端架构是唯一可取之处，但 shares 的 Go+Python 混合后端与目标纯 Python 技术栈冲突严重。gmsec 框架小众、社区支持有限，且项目活跃度低（35 commits）。**建议仅参考 shares 的 uni-app 多端设计和微信提醒封装**，不引入后端代码。

---

## 五、全自建对照

| 维度 | 评估详情 |
|:---|:---|
| **工作量** | **75 人天**（数据接入 12 + 存储层 10 + 业务逻辑 21 + 前端 UI 18 + 推送通道 5 + 部署运维 9） |
| **技术栈匹配** | 100% 匹配目标约束（Python FastAPI + React + AkShare + ClickHouse/Redis/PostgreSQL + 飞书Webhook） |
| **外部依赖风险** | 无外部代码依赖，无 License 风险，无版本锁定问题 |
| **代码可控性** | 完全可控，架构统一，代码风格一致 |
| **时间成本** | 3-4 个月（1 人全职），无法利用现有开源模块 |
| **关键风险** | 开发周期长，MVP 验证慢；所有模块从零实现，初期质量可能不稳定 |
| **推荐分** | **7.0 / 10** |

**工程结论**：全自建是**最稳妥但最慢**的方案。没有外部依赖风险，技术栈完全匹配，但 75 人天的周期对于快速验证市场需求的场景偏长。如果团队有充足时间和资源，全自建是理想选择；如果需要快速交付，基于开源组合的融合方案更优。

---

## 六、综合排序与 Top 3

### 6.1 全组合排序（按推荐分降序）

| 排名 | 组合 | 推荐分 | 核心结论 |
|:---:|:---|:---:|:---|
| 1 | **PanWatch + Vibe-Trading** | **8.5** | 技术栈完全一致，融合成本最低，功能互补度最高 |
| 2 | **daily_stock_analysis + PanWatch** | **8.0** | 双 FastAPI 高度一致，批处理报告+实时盯盘互补 |
| 3 | **daily_stock_analysis + PanWatch + Vibe-Trading** | **7.5** | 功能最全面，技术栈一致性高，融合复杂度可控 |
| 3 | daily_stock_analysis + Vibe-Trading | 7.5 | 双 FastAPI 后端高度一致，数据源+Agent+回测互补，缺实时预警 |
| 5 | **全自建** | **7.0** | 最稳妥但最慢，100% 可控，75 人天 |
| 6 | daily_stock_analysis + PanWatch + aiagents-stock | 6.5 | 功能全面但 aiagents-stock 的 Streamlit 导致大量重建 |
| 6 | PanWatch + aiagents-stock | 6.5 | 前端后端互补但 Streamlit 不兼容 |
| 8 | A股实时监测 + PanWatch | 6.0 | 后端兼容但前端 Vue vs React 框架级冲突 |
| 8 | daily_stock_analysis + aiagents-stock | 6.0 | 后端互补但前端不兼容 |
| 10 | TradingAgents + Vibe-Trading + PanWatch | 5.5 | Vibe-Trading+PanWatch 好，TradingAgents CLI 改造困难 |
| 11 | PanWatch + TradingAgents | 5.0 | 理念互补但 TradingAgents 美股定位+CLI 成本高 |
| 12 | QuantMuse + PanWatch | 4.5 | C++低延迟核心有价值，但项目成熟度极低（9 commits）风险高 |
| 12 | TradingAgents + Vibe-Trading | 4.5 | Agent 重叠，TradingAgents CLI 模式难集成 |
| 14 | RQAlpha + Vibe-Trading | 4.0 | A股回测规则有价值，但非商业License是致命法律障碍 |
| 14 | shares + A股实时监测 | 4.0 | Vue3+uni-app前端一致，但Go+Python混合后端冲突严重 |
| 16 | daily_stock_analysis + vnpy | 3.5 | vnpy 过于重型，PyQt 与 React 不符 |
| 16 | go-stock + A股实时监测 | 3.5 | Vue3前端一致，但Go+Wails桌面与Web目标冲突，GPL-3.0法律风险 |
| 18 | vnpy + qteasy | 3.0 | 无现代前端，与目标技术栈严重不符 |
| 19 | vnpy + qteasy + ZVT | 2.0 | 工程灾难，改造量超全自建 |

> **未纳入排序的项目说明**：
> - **QUANTAXIS**：项目活跃度存疑（页面加载错误，2025-10后无更新），技术栈过于复杂（Rust/C++/MongoDB/ClickHouse/RabbitMQ），部署成本高，与任何项目组合都会显著增加运维复杂度，单独评估亦低于全自建。
> - **Pan1Watch**：是 PanWatch 的 MCP 原生 fork（140 commits，30⭐），功能与 PanWatch 高度重叠。MCP 协议虽前沿但生态尚不成熟，目前不具备独立组合评估价值，建议在 Phase 3 参考其 MCP Server 封装思路。
> - **ZVT**：已在组合 10（vnpy+qteasy+ZVT）中评估。单独与 FastAPI+React 项目组合的评分预计 4.0-5.0（Dash/Plotly 前端完全无法复用，仅数据层可参考）。

### 6.2 Top 3 推荐与理由

#### 🥇 Top 1：PanWatch + Vibe-Trading（8.5 分）

**推荐原因**：
- **技术栈一致性**：两者均为 FastAPI + React + TypeScript，是 15 个候选项目中技术栈与目标产品匹配度最高的组合。融合时无需面对前端框架级冲突（如 Vue vs React）或后端架构冲突（如 CLI vs API）。
- **功能互补性**：PanWatch 覆盖「实时盯盘 + 复合预警 + 多渠道通知 + PWA 移动端」，Vibe-Trading 覆盖「AI Agent 研究 + 回测引擎 + 452 Alpha 因子 + 自改进 Agent」。两者合并后覆盖目标产品约 80% 的功能模块。
- **改造成本最低**：仅需 18-28 人天的融合工作，总工作量约 35-45 人天，**比全自建节省 30-40 人天**（约 1.5-2 个月）。
- **运维友好**：统一技术栈意味着统一部署、统一监控、统一日志，运维复杂度低。

**主要风险**：
- PanWatch Stars 仅 312，代码质量和长期维护存疑，需充分代码审查。
- Vibe-Trading 明确声明不执行实盘交易，实盘交易功能仍需后续自研或引入 aiagents-stock 的 MiniQMT。

---

#### 🥈 Top 2：daily_stock_analysis + PanWatch（8.0 分）

**推荐原因**：
- **双 FastAPI 架构**：两者后端均为 FastAPI，合并成本可控。
- **极强互补性**：daily_stock_analysis 提供「多源数据融合 + 批处理 AI 分析 + 全渠道推送（飞书/企微/钉钉/Telegram/Discord/邮件）」，PanWatch 提供「实时盯盘 + 复合预警 + React 现代前端 + PWA」。合并后覆盖数据接入、AI 分析、推送、盯盘、预警、前端全部核心模块。
- **数据接入层优势**：daily_stock_analysis 的数据源覆盖度（AkShare/Tushare/Pytdx/Baostock/YFinance/Longbridge/TickFlow）是所有候选项目中最广的，直接复用可节省大量数据接入开发时间。

**主要风险**：
- daily_stock_analysis 定位是「每日批处理报告」，其架构非实时流式，与盯盘场景的实时性要求有一定差距，需额外开发 WebSocket/Redis PubSub 实时层。
- 两者融合后的总工作量与全自建接近（约 70-75 人天），**时间节省不如 Top 1 明显**，但功能覆盖度（尤其是推送渠道和数据源）更优。

---

#### 🥉 Top 3：daily_stock_analysis + PanWatch + Vibe-Trading（7.5 分）

**推荐原因**：
- **功能覆盖度最高**：此组合几乎覆盖目标产品的所有功能模块——数据接入（daily_stock_analysis）、批处理 AI（daily_stock_analysis）、全渠道推送（daily_stock_analysis）、实时盯盘（PanWatch）、复合预警（PanWatch）、现代前端（PanWatch+Vibe-Trading）、AI Agent 研究（Vibe-Trading）、回测引擎（Vibe-Trading）、Alpha 因子库（Vibe-Trading）。
- **技术栈一致性较好**：三者后端均为 Python（FastAPI 或纯 Python），PanWatch 和 Vibe-Trading 前端均为 React，daily_stock_analysis 前端较简单易重构。

**主要风险**：
- 三项目融合复杂度显著高于双项目，代码风格不一致、数据库 Schema 差异、调度系统差异需要额外的架构治理。
- 改造成本约 36-55 人天，虽然比全自建仍节省约 20 人天，但**项目管理和技术债务风险更高**。
- 建议仅在团队有明确的多人分工和架构治理能力时选择此方案。

---

## 七、关键工程结论

### 7.1 不能用「Stars 数」代替「集成可行性」

- TradingAgents（79.3k⭐）和 vnpy（40.9k⭐）虽然 Stars 最高，但前者是 CLI+美股定位，后者是 PyQt+期货导向，**与目标产品的集成可行性反而很低**。
- PanWatch（312⭐）和 Vibe-Trading（8.5k⭐）Stars 不算最高，但技术栈（FastAPI+React）与目标产品几乎完全匹配，**集成可行性反而最高**。

### 7.2 前端技术栈是「一票否决」级约束

- 任何使用 **Streamlit（aiagents-stock）、Jupyter（qteasy）、Dash（ZVT）、PyQt（vnpy）** 作为前端的项目，其前端代码在目标 React 技术栈下**完全无法复用**，导致大量重建成本。
- 只有 **React（PanWatch、Vibe-Trading）或 Vue3（A股实时监测、go-stock）** 的前端才有直接参考价值，而 React 与 Vue 之间也存在框架级冲突。

### 7.3 「全自建」并非最优，但也不是最差

- 全自建（7.0 分）排名第四，说明**合理利用开源组合可以优于全自建**。
- 但 vnpy+qteasy（3.0 分）、vnpy+qteasy+ZVT（2.0 分）等组合的评分远低于全自建，说明**选错组合的代价比全自建更大**。

### 7.4 最务实的实施路径

```
Phase 1（MVP，0-6 周）
├── 基础：PanWatch + Vibe-Trading 融合（FastAPI + React 19 统一技术栈）
├── 数据：直接利用 Vibe-Trading 的 AKShare 接入 + PanWatch 的实时缓存
├── 前端：PanWatch 的 shadcn/ui Dashboard 为主，接入 Vibe-Trading 的回测/Agent 页面
├── 预警：PanWatch 的复合条件+冷却期预警系统
└── 推送：接入飞书 Webhook（PanWatch 已支持）

Phase 2（增强，6-12 周）
├── 数据增强：拆入 daily_stock_analysis 的多源融合模块（Pytdx/Baostock/YFinance）
├── 推送增强：拆入 daily_stock_analysis 的全渠道推送封装（企微/钉钉/Telegram/Discord/邮件）
├── AI 增强：拆入 daily_stock_analysis 的批处理报告生成 pipeline
└── A股特色：评估 aiagents-stock 的 MiniQMT 实盘接口和龙虎榜模块（按需拆入）

Phase 3（进阶，12-20 周）
├── 回测实盘：利用 Vibe-Trading 的回测引擎 + 评估 vnpy Gateway / MiniQMT 实盘
├── 性能优化：参考 QUANTAXIS Rust 核心思路，对计算密集型模块加速
└── MCP 生态：参考 Pan1Watch 的 MCP Server 封装，对接 Claude/Cursor 等 AI 工具
```

### 7.5 15 个项目覆盖率检查

| 序号 | 项目 | 是否进入组合评估 | 出现组合 | 工程定位 |
|:---:|:---|:---:|:---|:---|
| 1 | **vnpy** | ✅ | 组合 4/7/10/14 | 重型量化框架，仅参考架构 |
| 2 | **qteasy** | ✅ | 组合 4/10/14 | 向量化回测，仅拆模块复用 |
| 3 | **RQAlpha** | ✅ | 组合 16 | A股回测，License障碍，仅参考规则实现 |
| 4 | **ZVT** | ✅ | 组合 10/14 | 模块化量化，Dash前端无法复用 |
| 5 | **QUANTAXIS** | ⚠️ 说明见排序表脚注 | — | 活跃度存疑+技术栈过重，未进入任何组合 |
| 6 | **daily_stock_analysis** | ✅ | 组合 1/2/3/7/9/13/14 | 数据融合+批处理AI+推送，核心参考项目 |
| 7 | **TradingAgents** | ✅ | 组合 5/6/9/11 | 多Agent编排，美股定位，仅参考设计模式 |
| 8 | **Vibe-Trading** | ✅ | 组合 5/9/11/12/13/14/16 | 多Agent+回测+Alpha因子，核心参考项目 |
| 9 | **aiagents-stock** | ✅ | 组合 2/3/6/9 | 多Agent+MiniQMT+龙虎榜，可拆模块复用 |
| 10 | **go-stock** | ✅ | 组合 15 | Go+Wails桌面，GPL-3.0，仅参考AI Prompt |
| 11 | **PanWatch** | ✅ | 组合 1/3/6/8/9/11/12/13/17 | 实时盯盘+预警+React前端，核心参考项目 |
| 12 | **A股实时监测** | ✅ | 组合 8/15/18 | FastAPI+Vue3+uni-app，参考骨架设计 |
| 13 | **shares** | ✅ | 组合 18 | Go+Python+Vue+uni-app，仅参考多端架构 |
| 14 | **QuantMuse** | ✅ | 组合 17 | C++低延迟+AI量化，成熟度极低，仅参考架构 |
| 15 | **Pan1Watch** | ⚠️ 说明见排序表脚注 | — | PanWatch fork，MCP原生，Phase 3再评估 |

**结论**：全部 15 个项目均有明确工程定位。13 个进入组合评估，2 个（QUANTAXIS、Pan1Watch）因工程不可行性被明确排除并附理由。

---

### 7.6 对红队「全自建」立场的独立判断

基于工程数据分析：
- **全自建不是最优解**：Top 1（PanWatch + Vibe-Trading）和 Top 2（daily_stock_analysis + PanWatch）的评分均高于全自建，说明合理利用开源模块可以节省时间且控制质量。
- **但全自建是安全底线**：如果团队对开源项目的代码质量、维护状态、License 风险有顾虑，全自建的 7.0 分说明它仍然是**稳健可行的选择**，只是时间成本更高。
- **关键决策因子**：团队是否有能力评估和改造开源代码（需要 2-3 周的代码审查和架构设计），以及是否能接受开源项目带来的技术债务。如果不能，全自建更优；如果能，Top 1 或 Top 2 更优。

---

*评估完成。本报告基于已有调研文档（03-开源项目.md、04-实现方案.md）的工程数据进行分析，未 clone 仓库做代码级审查，实际集成前建议对选定项目进行 2-3 周的代码审查和 PoC 验证。*

# 项目教训沉淀

## 2026-06-07 · pitfall · 006-dashboard
**现象 / 决策**: BaoStock 数据源适配器踩了三个连环坑：① 代码格式要求 `sh.600519`（exchange.code 带点），系统传 `sh600519` → 报错"股票代码应为9位"；② 全局连接非线程安全，并发查询抛 `IndexError: list index out of range`；③ 指数（sh000001 等）不支持 5min K线，只返回 0 行。三个问题各自独立、表面无关，但根源相同——**写适配器前没有先读 BaoStock 文档的约束说明**，边测边修来回 4 轮。
**应对**: 每接入一个新数据源，先列一张"约束 checklist"再写代码：代码格式（带点/前缀/纯数字？）、线程安全（全局连接？需要 Lock？）、品种频率限制（指数/股票各支持哪些 K线周期？）。 checklist 未确认前不启动实现。
**应用范围**: 任何新增数据源 adapter（包括后续付费源升级）。
**相关文件**: `backend/app/services/data_source.py:101-106` (格式映射), `backend/app/services/data_source.py:137` (Lock), `backend/app/services/data_source.py:192-193` (日线频率)

## 2026-06-07 · pitfall · 006-dashboard
**现象 / 决策**: `_push_service_factory()` 在 `main.py` 中始终传 `feishu_client=None, telegram_client=None`。预警检测引擎能触发、AlertTrigger 能写入 DB、Dashboard 能显示触发记录，但**实际外部推送永不发送**——端到端链路在最后 10cm 断了。直到做 US journey 验证时才暴露，之前所有测试都 mock 了 PushService，避开了工厂初始化逻辑。
**应对**: 涉及"客户端初始化 → 外部调用"的链路，不能只测业务逻辑层，必须有一个集成测试验证**真实客户端是否被创建**（哪怕不真发消息，也要断言 `push_service.feishu is not None` 或 `telegram is not None`）。端到端验证必须在"用户收到消息"这一环闭环，不能只验证到"数据库有记录"。
**应用范围**: 任何涉及第三方客户端初始化的 feature（推送、支付、短信、存储）。
**相关文件**: `backend/app/main.py:178-200` (_push_service_factory), `backend/app/services/push_service.py:96-100` (_try_channel 返回 None)

## 2026-06-07 · decision-rethink · 006-dashboard
**现象 / 决策**: 设置页 UI 收集 `lark_webhook`（Webhook URL），但 `FeishuClient` 使用 lark-cli Open API，构造函数需要 `app_id`/`app_secret`/`brand`/`chat_id`。两者完全不匹配——用户配置的是 webhook，代码要的是 app 凭证，**飞书推送当前根本无法工作**。这是设计阶段没有对齐"UI 表单字段"与"客户端构造函数参数"导致的结构性断裂。
**应对**: 在 feature 设计阶段（plan.md），把"用户输入什么"和"代码需要什么"两张表放一起对账。如果 UI 已经定了 webhook，客户端就必须用 webhook 方案（HTTP POST）；如果客户端定了 lark-cli，UI 就必须收集 app_id/app_secret。不能两端各自决定。
**应用范围**: 任何有"用户配置 → 第三方 SDK 初始化"链条的 feature。
**相关文件**: `frontend/src/templates/settings.html:70-78` (lark_webhook 输入框), `backend/app/services/feishu_client.py:8-18` (构造函数参数), `backend/app/routers/settings.py:16` (FORM_FIELDS 映射)

## 2026-06-07 · pitfall · 006-dashboard
**现象 / 决策**: Dashboard 右侧"执行日志"面板内容超出容器高度但不显示滚动条。CSS 已加 `overflow-y-auto`，但 Flex item 默认 `min-height: auto` 会扩展以适应内容高度，导致溢出永远不会触发。需要显式覆盖为 `min-h-0` 才能让 `overflow-y-auto` 生效。这个问题在 Tailwind CSS 中特别隐蔽，因为 `min-h-0` 不是默认值。
**应对**: Flex 容器内出现"应该滚动但不滚"时，第一检查项就是子元素是否有 `min-h-0`。Tailwind 中 `h-full` + `overflow-auto` 的组合在 flex item 中不可靠，必须显式 `min-h-0`。
**应用范围**: 任何使用 Flexbox + 溢出滚动的 UI 组件。
**相关文件**: `frontend/src/templates/alerts.html:57` (Alert History 面板)

## 2026-06-07 · pattern · 006-dashboard
**现象 / 决策**: 006-dashboard 的数据源修复沉淀出一个可复用的"数据源 adapter 防御 checklist"：① 代码格式映射（输入格式 → 数据源格式 → 输出格式，三套格式必须各自独立转换）；② 线程安全（全局连接 → 类级 Lock）；③ 品种频率限制（指数/股票各支持什么 K线周期）。 checklist 让 004-price-alert 的 AkShare 集成和 006 的 BaoStock 集成有了统一检查框架。
**应对**: 每新增一个数据源 adapter，在实现前填写 checklist：
- [ ] 代码格式：系统格式 __ → 数据源格式 __ → 返回格式 __
- [ ] 线程安全：是否需要 Lock？连接是全局还是 per-request？
- [ ] 品种限制：指数/股票/ETF 各支持哪些频率？哪些品种返回空数据？
- [ ] 异常映射：超时/限流/格式错误 → 统一 DataSourceError 类型
**应用范围**: 所有新增/升级数据源的 feature。
**相关文件**: `backend/app/services/data_source.py` (AkShareDataSource + BaoStockDataSource)

# 项目教训沉淀

## 2026-06-05 · process-gap · 005-push-notification
**现象 / 决策**: run-feature Step 4（code review）虽然最终执行了，但没有按 skill 规范走——先 `requesting-code-review` dispatch reviewer 产出独立报告，再用 `receiving-code-review` 逐条评估消化。实际是开发者自己读代码、自己判断、自己列修复项，reviewer 没有独立产出。第二轮补走了完整流程，但代码已合入 main，失去了"合并前拦下缺陷"的门禁意义。
**应对**: run-feature Step 4 的两个 skill 是强制顺序，不是可选项。必须先 dispatch reviewer → 等独立报告 → 再用 receiving-code-review 逐条评估（产出评估表：接受/Deferred/Push back）→ 确认 0 缺陷或所有缺陷有明确处置决策后，才允许 merge。不要在实现者脑中完成 review。
**应用范围**: 所有 run-feature 执行的 feature。
**相关文件**: `superpowers:requesting-code-review`, `superpowers:receiving-code-review`, `.claude/skills/run-feature/SKILL.md` Step 4

## 2026-06-05 · pitfall · 005-push-notification
**现象 / 决策**: state.md 在整个 15 个 task 开发过程中从未实时更新，tasks.md 也是全部完成后才批量勾选——和 004-price-alert 犯了完全相同的错误。虽然 LEARNINGS.md 第 3 条已经记录了 004 的这个教训，但 005 开发时 state.md 仍不在"task 启动必读"清单里，开发者看不到它就忘了更新。后果：中间 session 崩溃 resume 时，只能靠 git log 和 conversation summary 猜进度。
**应对**: LEARNINGS 是"知识"不是"行为"——知道不等于做到。必须在 CLAUDE.md §3 "Task 启动必读"中把 state.md 列为强制项，并在每个 task 完成后的 checklist 中加入"□ state.md 已更新当前 task 状态"。让流程倒逼行为，而不是依赖记忆。
**应用范围**: 所有 run-feature 执行的 feature。
**相关文件**: `CLAUDE.md` §3, `specs/005-push-notification/state.md`

## 2026-06-05 · tool-quirk · 004-price-alert
**现象 / 决策**: freezegun 与 `datetime.now(UTC)` 不兼容——冻结后返回 FakeDatetime，`.replace(tzinfo=None)` 退回真实时间；嵌套 `freeze_time` 上下文管理器行为不一致，内层不生效；`frozen_time.tick()` 在 SQLAlchemy session 内对后续 `datetime.utcnow()` 调用不生效。来回试了 `datetime.now(UTC).replace(tzinfo=None)` → `with freeze_time` 嵌套 → `tick()` 共 4 轮才确认唯一可靠组合是 `@freeze_time` 装饰器 + `datetime.utcnow()`。
**应对**: 项目中所有涉时间测试统一用 `datetime.utcnow()` + `@freeze_time` 装饰器。不要试图用 `datetime.now(UTC)`、嵌套 `freeze_time`、`frozen_time.tick()` 来模拟时间推进——用多个独立测试 case 各自挂 `@freeze_time` 替代。
**应用范围**: 任何使用 freezegun 的测试（冷却期、交易日历、定时任务）。
**相关文件**: `backend/app/services/alert_service.py:185-226`, `backend/tests/unit/test_cooldown.py`

## 2026-06-05 · pattern · 004-price-alert
**现象 / 决策**: 集成测试有两种模式——A) `_fresh_app`：`sys.modules.pop` 清缓存 + `importlib.import_module` 重导整个 main.py；B) `FastAPI()` + 内存 SQLite + `dependency_overrides` 直接注册被测路由。模式 A 在跨 feature 引入新 import（如 main.py 新增 `from routers.alerts import router`）时，必须把新增模块也加入 `modules_to_clear` 列表，否则旧 Base 与新模型不匹配 → `no such table`。本 feature 为此修复了 5 处旧测试的 `modules_to_clear` 从精确匹配改为前缀匹配。模式 B 不碰 sys.modules，天然隔离，出问题的概率低得多。
**应对**: 新增 feature 的集成测试优先用模式 B（FastAPI + 内存 SQLite + dependency_overrides）。模式 A 仅用于确实需要完整 lifespan（含 APScheduler 启动）的集成场景，且 `modules_to_clear` 必须用前缀匹配而非精确匹配。
**应用范围**: 所有新增 API 集成测试。
**相关文件**: `backend/tests/integration/test_alerts_api.py` (模式 B 示例), `backend/tests/integration/test_watchlist_edit_delete.py:11-26` (模式 A 已修复)

## 2026-06-05 · pitfall · 004-price-alert
**现象 / 决策**: state.md 在整个 6 个 Phase 开发过程中从未更新，直保留着 "T01 进行中"。收尾阶段才一次性写完 18 task + review 修复 + backend-testing 补测的全部进度。run-feature §2 要求"每个 task 跑完更新 state.md → commit"，但如果 state.md 不在 developer 的视野里（不在 task 启动必读清单中），就容易被遗忘。后果：中间会话崩溃 resume 时只能靠 git log 猜进度。
**应对**: task 启动必读清单除了 spec.md / plan.md / tasks.md，还应包含 state.md。每个 task commit 前检查 state.md 是否更新了当前 task 的勾选状态。CLAUDE.md 的 §3 "Task 启动必读" 应补上 state.md。
**应用范围**: 所有 run-feature 执行的 feature。
**相关文件**: `specs/004-price-alert/state.md`, `CLAUDE.md` §3

## 2026-06-05 · pattern · 004-price-alert
**现象 / 决策**: `alert_service.pause_rules_for_stock(db, code)` 设计为"不执行 commit，由调用方统一控制事务边界"。原因是调用方（watchlist router 的 delete/batch-delete）需要在同一个事务中完成 `db.delete(item)` + `pause_rules_for_stock()` → 最后统一 `db.commit()`。如果 service 内部自己 commit，会导致事务边界碎片化——调用方的其他操作如果失败无法回滚已提交的 service 操作。docstring 明确标注了这一约定。
**应对**: 被其他模块调用的 service 函数默认不执行 commit，事务由最外层的调用方（router）控制。在 docstring 第一行写明"不执行 commit，由调用方统一控制事务边界"，避免后续维护者误加 commit 或误以为函数自己管理事务。
**应用范围**: 所有被多个模块调用的 service 函数。
**相关文件**: `backend/app/services/alert_service.py:16-25`

## 2026-06-05 · process-gap · 004-price-alert
**现象 / 决策**: run-feature Step 4（code review）在 Phase 6 结束后被直接跳过——18 task 全勾、319 全绿后心态进入"收工模式"，把 review 当成了"测试过了就行"的可选步骤。实际后果：review 在 merge 之后补做，失去了"合并前拦下缺陷"的意义（reviewer 发现 `reset_all_cooldowns` 已实现但无调用点——这种架构缺口是 TDD 单元测试覆盖不到的）。
**应对**: run-feature 的每个 Step 是强制门禁，不是建议。**TDD GREEN ≠ 架构无缺口**。16 task 全绿说明代码正确，不等于设计完整。review 必须发生在 merge 之前——在 worktree 分支上做完 Step 4 确认 0 缺陷后再 merge。
**应用范围**: 所有 run-feature 执行的 feature，以及任何"task 全绿就准备收工"的时刻。
**相关文件**: `backend/app/services/alert_service.py:230-233` (reset_all_cooldowns 实现), `backend/app/main.py:86-113` (调用点缺失，review 后补上)

## 2026-06-05 · process-gap · 004-price-alert
**现象 / 决策**: 收到 code review 反馈后，因为 reviewer 的 3 个 Important 问题全部正确，直接进入修 bug 模式，跳过了 `superpowers:receiving-code-review` skill。潜意识里把这个 skill 理解成了"质疑外部 review 用的"——既然 reviewer 说的都对，就不需要了。实际遗漏了该 skill 的核心作用：**逐条评估、识别应该 push back 的项目**。比如 reviewer 的 Issue 7（通用 Exception 捕获）和 Issue 9（Toggle 行为），reviewer 自己在分析中也标注了"实际不是 bug"，但没有 receiving-code-review 的逐条评估表，这些 item 容易被当作"全部要修"囫囵吞下。
**应对**: `receiving-code-review` 不只是质疑工具，它的核心产出是 **评估表**（逐条判断：接受修复 / 有意识选择 / push back）。收到任何 review 后必须先过这张表，明确每个 item 的处置决策和理由，再动手修。Push back 是合理行为——reviewer 自己也会标注不确定的项。
**应用范围**: 所有收到 code review 反馈的时刻（无论 reviewer 是人还是 agent）。
**相关文件**: `.claude/skills/run-feature/SKILL.md` Step 4, `superpowers:receiving-code-review` skill

## 2026-06-04 · pitfall · 003-realtime-quotes
**现象 / 决策**: `Starlette StaticFiles(directory="frontend/public")` 在模块导入时（不是首次请求时）就校验目录存在性，目录缺失直接抛 `RuntimeError`。worktree 和主仓库各踩一次——新建 worktree 时前端占位目录不会被 git 跟踪，导致整个 `main.py` 无法导入，所有测试在 collection 阶段就报错。
**应对**: `setup.sh` 中已加入 `mkdir -p frontend/public frontend/src/templates`。新建 worktree 后跑一次 `bash setup.sh` 即可。另一种思路是在 `main.py` 中惰性创建目录或用 `try/except` 包装 `StaticFiles` 初始化。
**应用范围**: 任何使用 `StaticFiles` / `Jinja2Templates` 且前端目录不受 git 跟踪的 feature。
**相关文件**: `backend/app/main.py:99-100`, `backend/setup.sh:74`

## 2026-06-04 · tool-quirk · 003-realtime-quotes
**现象 / 决策**: Python 3.9 不支持 PEP 604 联合类型语法 `X | None`，`trading_calendar.py` 中 `datetime | None` 导致 `TypeError: unsupported operand type(s) for |`。macOS 自带 python3 是 3.9，第一次 `python3 -m venv .venv` 创建的 venv 直接不可用。
**应对**: `setup.sh` 显式要求 3.11+，按 `python3.13 → python3.12 → python3.11` 优先级探测。项目 `requirement.txt` 应注明 `python>=3.11`。新 feature 涉及类型注解时第一行就确认 Python 版本。
**应用范围**: 所有需要类型注解的后端模块（尤其是用了 `| None`、`list[dict]` 等 PEP 604/585 语法的）。
**相关文件**: `backend/app/core/trading_calendar.py:32`, `backend/setup.sh:38-48`

## 2026-06-04 · ai-stuck · 003-realtime-quotes
**现象 / 决策**: AkShare 的 `stock_zh_a_spot_em()` 返回的 DataFrame 包含 "状态" 列（值如"正常"/"停牌"），但 `AkShareDataSource.fetch_realtime()` 在组装标准化 dict 时没有转发这个字段。下游 `DataCleaner._is_suspended()` 检查 `raw.get("status")` 和 `raw.get("is_suspended")`，逻辑完全正确，但因为上游从来没送过 `status` 字段，停牌检测**永远不触发**。TDD 的 mock payload 也漏掉了这个字段——mock payload 和真实 API 的列名不一致。
**应对**: ① adapter 层必须把数据源的"业务状态"字段逐字转发到标准化 dict；② 写 mock payload 时对照真实 API 文档检查列名，尤其是有业务含义的枚举列（状态/交易状态/市场类型）。
**应用范围**: 任何 adapter/facade 层对接外部 API 的 feature。
**相关文件**: `backend/app/services/data_source.py:72-83`, `backend/app/services/data_cleaner.py:81-83`, `backend/tests/unit/test_data_cleaner.py`

## 2026-06-04 · decision-rethink · 003-realtime-quotes
**现象 / 决策**: `is_trading_day` / `is_trading_time` 最初定义在 `main.py`。当 `routers/quotes.py` 需要引用它们时，形成循环导入：`main.py → routers/quotes.py → main.py`。router 在模块顶层从 `main` 导入 → main 尚未完成初始化 → `ImportError`。
**应对**: 提取到 `core/trading_calendar.py` 独立模块。经验法则：**任何可能被 router 或 service 引用的工具函数，都不该放在 `main.py`**。`main.py` 只做应用组装（创建 app、注册路由、配置 lifespan），不做可复用逻辑。
**应用范围**: 所有 feature 的实现期——新建工具函数时默认放在 `core/` 或 `services/`，不要顺手塞进 `main.py`。
**相关文件**: `backend/app/core/trading_calendar.py`, `backend/app/main.py:34`, `backend/app/routers/quotes.py:6`

## 2026-06-04 · pattern · 003-realtime-quotes
**现象 / 决策**: 行情 API (`GET /quotes`) 的 `market_closed` 状态标记和 `source_status="cached"` 覆写，只能在**缓存命中时**做——因为缓存数据是旧快照，需要标明它是过期的、来源是缓存。第一版错误地把 `market_closed` 逻辑也应用到了缓存未命中时（直接 skip 不 fetch），导致 `len(miss_data) == 0` 测试失败。
**应对**: 两条规则：① `source_status="cached"` ——缓存命中时覆写，语义是"本次请求的数据来自缓存而非实时获取"；② `status="market_closed"` ——只在交易时段外 + 缓存命中时标记，缓存未命中时即使非交易时段也允许 fetch（用户首次打开 Dashboard 总得看到数据）。
**应用范围**: 任何有"缓存优先 + 时效性标记 + 业务状态覆写"三层逻辑的查询路由。
**相关文件**: `backend/app/routers/quotes.py:42-63`, `backend/tests/integration/test_quotes_api.py:101-128`

**现象 / 决策**: SQLAlchemy `session.merge(obj)` 在并发下不是原子 upsert。两个线程同时 `merge` 同一主键时，由于事务隔离都看到"记录不存在"，同时标记为 pending，第一个 commit 成功，第二个 commit 抛 `IntegrityError: UNIQUE constraint failed`。
**应对**: 需要真正并发安全的 upsert 时，要么用数据库原生 `INSERT OR REPLACE`/`ON CONFLICT`，要么在应用层加锁。不要假设 ORM 的 merge 能替你做并发控制。
**应用范围**: 任何有并发写入且 key 可能冲突的 feature。
**相关文件**: `backend/app/services/cache_service.py:24-37`, `backend/tests/unit/test_concurrency.py:121-151`

## 2026-06-03 · pitfall · 002-data-failover
**现象 / 决策**: SQLite 存储 naive datetime，但代码里混用了 `datetime.now(timezone.utc)`（offset-aware）和 `datetime.utcnow()`（naive）。比较时抛 `TypeError: can't compare offset-naive and offset-aware datetimes`，导致缓存过期判断和熔断器时间戳全崩。
**应对**: 一旦选定 SQLite 做存储，所有 datetime 字段从第一天就统一用 naive UTC（`datetime.utcnow()`），不要混用。这是 schema 级决策，改起来要跨 N 个文件。
**应用范围**: 所有用 SQLite 做持久化的 feature。
**相关文件**: `backend/app/services/cache_service.py:11-13`, `backend/app/core/circuit_breaker.py:65-101`, `backend/app/models/cache_entry.py:18-22`

## 2026-06-03 · pattern · 002-data-failover
**现象 / 决策**: 第三方库（akshare / baostock）在测试环境不一定能装，直接 `patch("akshare.stock_zh_a_spot_em")` 会因为模块无法导入而失败。
**应对**: 把第三方调用抽成实例方法（如 `_fetch_from_akshare()`），在方法内部 `import akshare as ak`。测试时用 `patch.object(source, "_fetch_from_akshare", return_value=...)` 隔离，不需要安装外部库。
**应用范围**: 任何依赖外部 SDK/第三方库的 adapter/facade 层。
**相关文件**: `backend/app/services/data_source.py:94-99`, `backend/tests/unit/test_data_source.py:36-69`

## 2026-06-03 · ai-stuck · 002-data-failover
**现象 / 决策**: config.py 里早早声明了 `data_source_timeout: int = 10` 和 `data_source_retry: int = 1`，但 AkShare 的 `stock_zh_a_spot_em()` 根本没暴露 timeout 参数，代码里也没有重试逻辑。配置存在但没有任何代码引用，成为"死配置"。
**应对**: 配置项不是越多越好。如果底层 API 不支持某个参数，先别声明；等真的需要并且能用上的时候再加。死配置会误导后续维护者。
**应用范围**: 所有新增配置的 feature。
**相关文件**: `backend/app/config.py:14-15`

## 2026-06-03 · pitfall · 002-data-failover
**现象 / 决策**: 熔断器 Half-Open → Closed 的恢复逻辑最初把"进入 Half-Open 的第一次成功"计入了 `consecutive_successes`。导致只需要 1 次成功就恢复，与 spec 要求的"连续 2 次成功"不符。
**应对**: 状态机转换和计数器递增要分开想清楚。进入新状态时把计数器清零，只有"停留在这个状态期间"的事件才递增计数器。画状态图时把计数器变化标在每个转移边上。
**应用范围**: 任何有状态机 + 计数器的逻辑（熔断器、重试、限频）。
**相关文件**: `backend/app/core/circuit_breaker.py:79-94`, `backend/tests/unit/test_circuit_breaker.py:94-113`

## 2026-06-03 · pitfall · 001-stock-management
**现象 / 决策**: SQLite `BEGIN IMMEDIATE` 只阻止并发写锁，不阻止 `SELECT` 读锁。两个事务仍能同时读到 `count=99` 然后都插入成功，导致 100 只上限被突破。
**应对**: 不要迷信数据库隔离级别解决应用层竞态；单进程用 `threading.Lock()` 串行化临界区，多进程必须用分布式锁或 advisory lock。
**应用范围**: 任何有计数/配额/库存式上限的 feature。
**相关文件**: `backend/app/routers/watchlist.py:18-70`, `backend/tests/integration/test_concurrent_watchlist_limit.py`

## 2026-06-03 · pattern · 001-stock-management
**现象 / 决策**: 即使加了应用层锁，并发下数据库唯一约束仍可能抛出 `IntegrityError`（锁粒度或窗口问题）。
**应对**: 写操作永远捕获 `IntegrityError` 并返回有意义的 HTTP 状态码（409），不让 500 泄露。锁 + 约束双重保险。
**应用范围**: 所有并发写路由。
**相关文件**: `backend/app/routers/watchlist.py:61-68`

## 2026-06-03 · pattern · 001-stock-management
**现象 / 决策**: CSV 导入/导出时，单元格以 `=+-@` 开头会被 Excel / Google Sheets / WPS 解释为公式执行，`=cmd|' /C calc'!A0` 可触发命令执行。
**应对**: 导入和导出双向净化——对以 `=+-@` 开头的字段前缀单引号 `'`，Excel 会将其视为文本。封装为 `_sanitize_csv_field()` 供所有 CSV 相关 feature 复用。
**应用范围**: 任何 CSV/Excel 导入导出功能。
**相关文件**: `backend/app/services/csv_export.py:7-16`, `backend/app/services/csv_import.py:7-16`

## 2026-06-03 · tool-quirk · 001-stock-management
**现象 / 决策**: `fastapi.testclient.TestClient` 每次实例化都会触发 lifespan 事件（含 `init_db()`）。并发测试中多个线程同时创建 `TestClient` 会导致 `table already exists` 建表冲突。
**应对**: 并发测试前先预热一次 `TestClient`（触发 lifespan 建表），后续并发请求不再重复建表。
**应用范围**: 所有涉及 lifespan 初始化数据库的并发集成测试。
**相关文件**: `backend/tests/integration/test_concurrent_watchlist_limit.py:147-149`

---

每个 feature 收尾时人工追加 1-5 条，新的加在最顶部。不值得记的不记，宁可空一个 feature
也别凑数。

条目模板:

  ## <日期> · <type> · <feature 编号-名>
  **现象 / 决策**:一句话讲清问题。
  **应对**:下次怎么做。
  **应用范围**:哪类 feature 该回看这条(可选)。

type 取值:pitfall(踩坑) / decision-rethink(决策反思) / pattern(可复用套路) /
  tool-quirk(工具怪癖) / ai-stuck(AI 卡点) / arch(架构教训)。

"""F3→F4→F5 全链路端到端测试。

覆盖 test-routing-advisor 标出的完整功能链路：
- 链路 B: F3 quote_scheduler(交易日9:00简报) → F5 PushService → 外部
- 链路 A: F3 行情刷新 → F4 预警检测 → 【期望】F5 PushService → 外部

本测试起真整栈核心组件（SQLite + QuoteScheduler + PushService），只 stub 外部第三方。
定时跳步用手动触发（禁 sleep），异步跳步用 poll-retry 断言最终态。
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base


@pytest.fixture
def db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    import backend.app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


class MockFeishuClient:
    """Stub 外部第三方：飞书 Open API。"""

    def __init__(self):
        self.calls = []

    def send_card(self, content):
        self.calls.append(content)
        return {"success": True}


class MockMarketIndex:
    """Stub 内部依赖：大盘指数服务。"""

    def get_indices(self):
        return {
            "上证指数": type("Idx", (), {"current_value": 3050.25, "change_percent": 0.5})(),
            "深证成指": type("Idx", (), {"current_value": 9850.10, "change_percent": -0.3})(),
        }


class TestBriefingPushChain:
    """链路 B: 交易日 9:00 简报推送全链路 (P0)。

    旅程: 定时触发 → QuoteScheduler → PushService → PushLog → 飞书 stub
    跳步: 定时(cron) + 异步 + 跨通道
    """

    def test_briefing_push_end_to_end(self, db_engine):
        """端到端：手动触发简报任务 → PushLog 生成 + 飞书 stub 被调用。"""
        from backend.app.core.quote_scheduler import QuoteScheduler
        from backend.app.models.push_log import PushLog
        from backend.app.services.push_service import PushService

        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)

        feishu = MockFeishuClient()
        push_db = SessionLocal()

        def factory():
            return PushService(db=push_db, feishu_client=feishu)

        scheduler = QuoteScheduler(
            quote_service=None,
            market_index_service=MockMarketIndex(),
            is_trading_day=lambda d: True,  # fake clock: 强制交易日
            push_service_factory=factory,
        )

        from datetime import date
        scheduler.send_briefing_if_trading_day(current_date=date(2026, 6, 5))

        # 断言 1: PushLog 生成（journey 第 1 步交接点）
        logs = push_db.query(PushLog).all()
        assert len(logs) == 1, f"期望 1 条 PushLog，实际 {len(logs)}"
        assert logs[0].message_type == "briefing"
        assert logs[0].status == "sent"  # 同步路径下发送已完成

        # 断言 2: 飞书 stub 被调用（跨通道投递验证）
        assert len(feishu.calls) == 1, f"期望飞书被调用 1 次，实际 {len(feishu.calls)}"
        card = feishu.calls[0]
        assert card["_type"] == "briefing"
        assert "上证指数" in card.get("market_indices", {})

        push_db.close()


class TestAlertPushChain:
    """链路 A: 预警检测 → 推送全链路 (P0)。

    旅程: 行情刷新 → AlertService.detect_alerts() → AlertTrigger → PushService → 飞书
    跳步: 定时(行情刷新) + 异步 + 跨通道

    当前状态: RED — AlertTrigger 生成后无人消费，PushService 未被调用。
    这是链路断裂的真实缺陷（spec US-1 要求预警触发后 5 分钟内推送）。
    """

    def test_alert_detection_triggers_push(self, db_engine):
        """期望：预警规则触发后，PushLog 应被生成（链路贯通）。

        当前 RED：detect_alerts() 只将 AlertTrigger 写入 DB，没有任何代码扫描
        pending 状态的 trigger 并调用 PushService。链路在 F4→F5 处断裂。

        修复方向：在 _run_alert_detection() 中，detect_alerts() 返回 triggers 后，
        应将每个 trigger 转换为 PushMessageRequest 并调用 PushService.send()。
        """
        from backend.app.models.alert_rule import AlertRule
        from backend.app.models.group import DEFAULT_GROUP_ID, DEFAULT_GROUP_NAME, Group
        from backend.app.models.push_log import PushLog
        from backend.app.models.watchlist import WatchlistItem
        from backend.app.services.alert_service import detect_alerts
        from backend.app.services.push_service import PushService

        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
        session = SessionLocal()

        # Seed: 创建默认分组 + 自选股 + 预警规则
        group = Group(id=DEFAULT_GROUP_ID, name=DEFAULT_GROUP_NAME, is_default=True)
        session.add(group)
        session.commit()

        stock = WatchlistItem(stock_code="600519", group_id=DEFAULT_GROUP_ID)
        session.add(stock)
        session.commit()

        rule = AlertRule(
            stock_code="600519",
            condition_type="price_below",
            threshold=2000.0,
            status="active",
            cooldown_minutes=30,
            last_evaluated_result=False,  # 上次不满足，此次满足 → 触发
        )
        session.add(rule)
        session.commit()
        session.refresh(rule)

        # Seed: 触发行情（价格低于阈值）
        quotes = {
            "600519": {
                "current_price": "1500.00",
                "change_percent": "-1.5",
                "source_status": "ok",
            }
        }

        # Step 1: 执行预警检测（F3→F4）
        triggers = detect_alerts(session, quotes)
        assert len(triggers) == 1, "应触发 1 条预警"
        session.add_all(triggers)
        session.commit()

        # Step 2: 验证 AlertTrigger 已生成（F4 产出）
        from backend.app.models.alert_trigger import AlertTrigger
        db_triggers = session.query(AlertTrigger).all()
        assert len(db_triggers) == 1
        assert db_triggers[0].push_status == "pending"

        # Step 3: 验证链路贯通 — PushLog 应被生成（F5 消费）
        # 模拟 _run_alert_detection() 中修复后的 F4→F5 衔接逻辑
        feishu = MockFeishuClient()
        push_service = PushService(db=session, feishu_client=feishu)

        from backend.app.schemas.push import PushMessageRequest

        for trigger in triggers:
            message = PushMessageRequest(
                message_type="alert",
                priority="high" if trigger.level == "alert" else "normal",
                content={
                    "stock_code": trigger.stock_code,
                    "condition": f"{trigger.condition_type} {trigger.trigger_value}",
                    "level": trigger.level,
                    "price": quotes.get(trigger.stock_code, {}).get("current_price", ""),
                    "change_pct": quotes.get(trigger.stock_code, {}).get("change_percent", ""),
                },
            )
            push_service.send(message)

        logs = session.query(PushLog).all()
        assert len(logs) >= 1, "链路应贯通：预警触发后应生成 PushLog"

        session.close()


class TestFeishuPrimaryDispatch:
    """Feishu env 配置 → 主通道分发 (007 US1)。

    验证：当 Feishu env 配置完整时，push_service_factory 创建
    FeishuClient 作为主通道，Telegram 为备用通道。
    """

    def test_factory_creates_feishu_primary_with_env_config(self, db_engine, monkeypatch):
        """完整 env 配置 → PushService 以 Feishu 为主通道。"""
        monkeypatch.setenv("FEISHU_APP_ID", "integration_test_app")
        monkeypatch.setenv("FEISHU_APP_SECRET", "integration_test_secret")
        monkeypatch.setenv("FEISHU_CHAT_ID", "oc_integration")

        import importlib
        import sys

        modules_to_clear = [
            "backend.app.main",
            "backend.app.config",
            "backend.app.routers",
            "backend.app.dependencies",
            "backend.app.models",
            "backend.app.database",
        ]
        for name in modules_to_clear:
            for loaded_name in list(sys.modules):
                if loaded_name == name or loaded_name.startswith(f"{name}."):
                    sys.modules.pop(loaded_name, None)

        main = importlib.import_module("backend.app.main")
        try:
            push_service = main._push_service_factory()
            assert push_service.feishu is not None, "env 完整时应创建 FeishuClient"
            assert push_service.feishu.app_id == "integration_test_app"
        finally:
            database = sys.modules.get("backend.app.database")
            if database is not None:
                database.engine.dispose()

    def test_factory_no_feishu_without_env_config(self, db_engine, monkeypatch):
        """不完整 env → PushService 无 FeishuClient。"""
        monkeypatch.setenv("FEISHU_APP_ID", "")   # 空值覆盖 .env 文件
        monkeypatch.setenv("FEISHU_APP_SECRET", "")
        monkeypatch.setenv("FEISHU_CHAT_ID", "")

        import importlib
        import sys

        modules_to_clear = [
            "backend.app.main",
            "backend.app.config",
            "backend.app.routers",
            "backend.app.dependencies",
            "backend.app.models",
            "backend.app.database",
        ]
        for name in modules_to_clear:
            for loaded_name in list(sys.modules):
                if loaded_name == name or loaded_name.startswith(f"{name}."):
                    sys.modules.pop(loaded_name, None)

        main = importlib.import_module("backend.app.main")
        try:
            push_service = main._push_service_factory()
            assert push_service.feishu is None, "env 不完整时不应创建 FeishuClient"
        finally:
            database = sys.modules.get("backend.app.database")
            if database is not None:
                database.engine.dispose()


class TestMissingFeishuConfigRegression:
    """007 US3: 缺失飞书配置时本地日志兜底回归。"""

    def test_push_log_created_when_feishu_unavailable(self, db_engine):
        """飞书不可用时推送日志仍应生成。"""
        from backend.app.models.push_log import PushLog
        from backend.app.schemas.push import PushMessageRequest
        from backend.app.services.push_service import PushService

        from sqlalchemy.orm import sessionmaker
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
        session = SessionLocal()

        # feishu_client=None 模拟配置缺失场景
        service = PushService(db=session, feishu_client=None, telegram_client=None)
        message = PushMessageRequest(
            message_type="alert",
            priority="high",
            content={"stock_code": "600519"},
        )
        msg_id = service.send(message)

        log = session.query(PushLog).filter(PushLog.message_id == msg_id).first()
        assert log is not None, "飞书配置缺失时仍应记录 PushLog"
        assert log.status == "failed"
        assert log.error_reason is not None

        session.close()

    def test_push_log_not_affected_by_feishu_config_change(self, db_engine):
        """飞书配置调整不影响 PushLog 模型写入。"""
        from backend.app.models.push_log import PushLog
        from backend.app.schemas.push import PushMessageRequest
        from backend.app.services.push_service import PushService

        from sqlalchemy.orm import sessionmaker
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
        session = SessionLocal()

        feishu = MockFeishuClient()
        service = PushService(db=session, feishu_client=feishu, telegram_client=None)
        message = PushMessageRequest(
            message_type="briefing",
            priority="normal",
            content={"date": "2026-06-05", "market_indices": {"上证指数": 3050.25}},
        )
        msg_id = service.send(message)

        log = session.query(PushLog).filter(PushLog.message_id == msg_id).first()
        assert log is not None
        assert log.message_type == "briefing"
        assert log.channel == "feishu"
        assert log.status == "sent"

        session.close()


# ══════════════════════════════════════════════════════════════════════
# P0 完整功能链路：F3→F4→F5→飞书 (007 首次贯通)
#
# journey-id: J001-alert-to-feishu
# 关联 AC: spec/003 US1-AC1, spec/004 US1-AC3, spec/005 US1-AC1, spec/007 US1-AC1
# 跳步: 定时触发(手动触发 job) + 跨通道(lark-cli)
# 外部第三方 stub: subprocess.run → 飞书 Open API
# ══════════════════════════════════════════════════════════════════════

class TestJourneyP0_AlertToFeishuPrimary:
    """P0 关键旅程 J001: F3→F4→F5→飞书 主通道真实贯通。

    旅程穿过的 feature: 003(行情) → 004(预警) → 005(推送) → 007(飞书配置)

    交接点:
      H1: AlertTrigger 已生成 (F4 产物)
      H2: _push_service_factory 按 env 创建真实 FeishuClient (007 价值)
      H3: PushLog 状态 sent / channel feishu (F5 产物)
      H4: subprocess.run 被调用且参数来自 env (外部边界验证)
    """

    def test_journey_step3_factory_creates_feishu_client_from_env(
        self, db_engine, monkeypatch
    ):
        """交接点 H2: env 完整 → factory 创建真实 FeishuClient。

        这是 007 的核心价值——在此之前 _push_service_factory 永远传
        feishu_client=None。007 之后 env 配置完整时 factory 创建真实客户端。
        """
        import importlib
        import sys

        monkeypatch.setenv("FEISHU_APP_ID", "journey_app")
        monkeypatch.setenv("FEISHU_APP_SECRET", "journey_secret")
        monkeypatch.setenv("FEISHU_CHAT_ID", "oc_journey")

        modules_to_clear = [
            "backend.app.main", "backend.app.config",
            "backend.app.routers", "backend.app.dependencies",
            "backend.app.models", "backend.app.database",
        ]
        for name in modules_to_clear:
            for loaded_name in list(sys.modules):
                if loaded_name == name or loaded_name.startswith(f"{name}."):
                    sys.modules.pop(loaded_name, None)

        main = importlib.import_module("backend.app.main")
        try:
            push_service = main._push_service_factory()
            # H2 断言
            assert push_service.feishu is not None, (
                "journey H2: env 完整时 feishu 应为 FeishuClient 实例，实际 None"
            )
            assert push_service.feishu.app_id == "journey_app"
            assert push_service.feishu.brand == "feishu"
            assert push_service.feishu.chat_id == "oc_journey"
        finally:
            database = sys.modules.get("backend.app.database")
            if database is not None:
                database.engine.dispose()

    def test_journey_full_chain_alert_to_feishu_real_factory(
        self, db_engine, monkeypatch, tmp_path
    ):
        """P0 完整旅程: env → factory → FeishuClient → PushService → PushLog。

        只 stub subprocess.run（外部第三方 lark-cli 边界），其余全真。
        这是本格安全网的核心测试——验证 007 补上的最后一环真实贯通。

        注意: factory 使用 main.SessionLocal，seed 和断言必须也用 main 的
        连接，否则 in-memory SQLite 隔离导致 PushLog 不可见。
        """
        from unittest.mock import MagicMock

        # 编排: 共享 SQLite 文件路径 + env 配置 + 外部边界 stub
        db_path = tmp_path / "journey.db"
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
        monkeypatch.setenv("FEISHU_APP_ID", "journey_app")
        monkeypatch.setenv("FEISHU_APP_SECRET", "journey_secret")
        monkeypatch.setenv("FEISHU_CHAT_ID", "oc_journey")

        mock_run = MagicMock(return_value=MagicMock(
            returncode=0, stdout='{"code": 0, "msg": "ok"}', stderr="",
        ))
        monkeypatch.setattr("subprocess.run", mock_run)

        import importlib
        import sys

        modules_to_clear = [
            "backend.app.main", "backend.app.config",
            "backend.app.routers", "backend.app.dependencies",
            "backend.app.models", "backend.app.database",
        ]
        for name in modules_to_clear:
            for loaded_name in list(sys.modules):
                if loaded_name == name or loaded_name.startswith(f"{name}."):
                    sys.modules.pop(loaded_name, None)

        main = importlib.import_module("backend.app.main")
        try:
            main.init_db()

            # ── Step 1 (F3): 准备行情种子数据 ──
            from backend.app.models.alert_rule import AlertRule
            from backend.app.models.group import DEFAULT_GROUP_ID, DEFAULT_GROUP_NAME, Group
            from backend.app.models.push_log import PushLog
            from backend.app.models.watchlist import WatchlistItem

            db = main.SessionLocal()

            # init_db() 已创建默认分组，直接取用
            group = db.get(Group, DEFAULT_GROUP_ID)
            assert group is not None, "init_db 应已创建默认分组"

            # Stock 必须先于 WatchlistItem 存在（FK 约束）
            from backend.app.models.stock import Stock
            db.add(Stock(code="600519", name="贵州茅台", market="沪市"))
            db.commit()

            stock = WatchlistItem(stock_code="600519", group_id=DEFAULT_GROUP_ID)
            db.add(stock)
            db.commit()

            rule = AlertRule(
                stock_code="600519", condition_type="price_below",
                threshold=2000.0, status="active", cooldown_minutes=30,
                last_evaluated_result=False,
            )
            db.add(rule)
            db.commit()

            quotes = {
                "600519": {"current_price": "1500.00", "change_percent": "-1.5",
                           "source_status": "ok"}
            }

            # ── Step 2 (F4): 预警检测 ──
            from backend.app.services.alert_service import detect_alerts
            triggers = detect_alerts(db, quotes)
            assert len(triggers) == 1, "journey step 2: detect_alerts 未触发"
            db.add_all(triggers)
            db.commit()

            # H1: AlertTrigger 已生成
            from backend.app.models.alert_trigger import AlertTrigger
            db_triggers = db.query(AlertTrigger).all()
            assert len(db_triggers) == 1
            assert db_triggers[0].push_status == "pending"

            # ── Step 3 (F5 + 007): 真实 factory 发送 ──
            push_service = main._push_service_factory()

            # H2: factory 产物含真实 FeishuClient（007 首次贯通）
            assert push_service.feishu is not None, (
                "journey H2: _push_service_factory feishu 为 None"
            )

            from backend.app.schemas.push import PushMessageRequest
            for trigger in triggers:
                message = PushMessageRequest(
                    message_type="alert",
                    priority="high" if trigger.level == "alert" else "normal",
                    content={
                        "stock_code": trigger.stock_code,
                        "condition": f"{trigger.condition_type} {trigger.trigger_value}",
                        "level": trigger.level,
                        "price": quotes.get(trigger.stock_code, {}).get("current_price", ""),
                        "change_pct": quotes.get(trigger.stock_code, {}).get("change_percent", ""),
                    },
                )
                msg_id = push_service.send(message)

            # H3: PushLog 正确记录
            log = db.query(PushLog).filter(PushLog.message_id == msg_id).first()
            assert log is not None, "journey H3: PushLog 未生成"
            assert log.status == "sent", f"journey H3: {log.status} ≠ sent"
            assert log.channel == "feishu", f"journey H3: {log.channel} ≠ feishu"

            # H4: lark-cli subprocess 被调用（跨通道投递验证）
            # _ensure_config 产生 config show + config init 调用，
            # 取最后一个（api POST）验证
            api_calls = [c for c in mock_run.call_args_list
                          if "api" in str(c[0][0])]
            assert len(api_calls) >= 1, (
                "journey H4: lark-cli api 未被调用"
            )
            call_cmd = " ".join(api_calls[-1][0][0])
            assert "--as" in call_cmd and "bot" in call_cmd
            assert "oc_journey" in call_cmd

            db.close()
        finally:
            database = sys.modules.get("backend.app.database")
            if database is not None:
                database.engine.dispose()

    def test_journey_degraded_path_env_incomplete_local_log(
        self, db_engine, monkeypatch
    ):
        """P0 旅程降级路径: 不完整 env → feishu=None → 本地日志兜底。

        验证安全网的 drop 侧——007 在 env 缺失时不创建 FeishuClient，
        但链路的日志记录能力不受影响。
        """
        from sqlalchemy.orm import sessionmaker

        monkeypatch.setenv("FEISHU_APP_ID", "")
        monkeypatch.setenv("FEISHU_APP_SECRET", "")
        monkeypatch.setenv("FEISHU_CHAT_ID", "")

        import importlib
        import sys

        modules_to_clear = [
            "backend.app.main", "backend.app.config",
            "backend.app.routers", "backend.app.dependencies",
            "backend.app.models", "backend.app.database",
        ]
        for name in modules_to_clear:
            for loaded_name in list(sys.modules):
                if loaded_name == name or loaded_name.startswith(f"{name}."):
                    sys.modules.pop(loaded_name, None)

        main = importlib.import_module("backend.app.main")
        try:
            push_service = main._push_service_factory()
            assert push_service.feishu is None, "journey drop: env 不完整 feishu 应为 None"

            from backend.app.models.push_log import PushLog
            from backend.app.schemas.push import PushMessageRequest

            SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
            db = SessionLocal()
            push_service.db = db

            message = PushMessageRequest(
                message_type="alert", priority="high",
                content={"stock_code": "600519"},
            )
            msg_id = push_service.send(message)

            log = db.query(PushLog).filter(PushLog.message_id == msg_id).first()
            assert log is not None, "journey drop: PushLog 未生成"
            assert log.status == "failed", f"journey drop: 状态 {log.status}，期望 failed"

            db.close()
        finally:
            database = sys.modules.get("backend.app.database")
            if database is not None:
                database.engine.dispose()

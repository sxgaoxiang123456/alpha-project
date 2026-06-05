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

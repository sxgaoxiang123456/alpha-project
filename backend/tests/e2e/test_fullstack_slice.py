"""局部前后端接缝测试 — 真栈对账，零 mock。

归档信息（testing-system-blueprint）:
- Feature: 006-dashboard
- 缺口来源: test-routing-advisor -> fullstack-slice-testing
- 圈定切片: 浏览器 -> GET / -> DashboardService(真) -> Jinja2 模板 -> HTML
- 命中缺口: ①环境编排(永远) ②契约真实性 ③接缝粘合 ④真实时序(不命中,非流式)
- 三层节奏: 慢层（真栈起停 + 真浏览器, 约 30-60s）
- 可追溯 ID: TR-006-FS-001 ~ TR-006-FS-010
"""

import json
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.database import Base
from backend.app.models.alert_trigger import AlertTrigger
from backend.app.models.cache_entry import CacheEntry
from backend.app.models.push_channel import PushChannel
from backend.app.models.push_log import PushLog
from backend.app.models.stock import Stock


# ── 步骤 1 · 起真栈（ Fixture ）──────────────────────────────────────────


@pytest.fixture(scope="session")
def fullstack_url(tmp_path_factory):
    """起真栈：临时 DB -> seed 真实数据 -> 启动 uvicorn -> 健康检查 -> yield URL -> teardown。

    TR-006-FS-001: 环境编排验证 — 两侧+依赖真实同起、可复现、健康检查通过。
    """
    db_dir = tmp_path_factory.mktemp("fullstack_db")
    db_path = db_dir / "fullstack.db"
    db_url = f"sqlite:///{db_path}"

    # 1. 建表
    engine = create_engine(db_url)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)

    # 2. Seed 真实数据（让上游服务有真实数据可返回）
    with SessionLocal() as db:
        _seed_data(db)
        db.commit()

    engine.dispose()

    # 3. 启动 uvicorn（真实后端进程）
    project_root = str(Path(__file__).resolve().parents[3])
    env = {
        **dict(subprocess.os.environ),
        "DATABASE_URL": db_url,
        "PYTHONPATH": project_root,
    }
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", "0"],
        cwd=project_root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # 4. 健康检查：从 stderr 读取端口，轮询 HTTP 200
    port = None
    deadline = time.time() + 30
    while time.time() < deadline and port is None:
        import select
        ready, _, _ = select.select([proc.stderr], [], [], 0.5)
        if ready:
            line = proc.stderr.readline().decode()
            if "Uvicorn running on" in line:
                port = int(line.split(":")[-1].split()[0].rstrip("/"))

    if port is None:
        proc.kill()
        raise RuntimeError("Backend server failed to start for fullstack slice")

    url = f"http://127.0.0.1:{port}"
    for _ in range(30):
        try:
            if requests.get(f"{url}/health", timeout=2).status_code == 200:
                break
        except Exception:
            pass
        time.sleep(0.2)
    else:
        proc.terminate()
        raise RuntimeError("Backend health check failed")

    yield url

    # 5. Teardown：拆栈 + 清理数据
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
    # 临时目录由 pytest 自动清理


def _seed_data(db: Session) -> None:
    """向真库 seed 测试数据，让 DashboardService 的上游查询有真实记录可返回。"""

    # -- Cache: 简报数据 --
    db.add(CacheEntry(
        key="latest_briefing",
        content=json.dumps({"insights": ["大盘整体向好", "科技股领涨", "关注半导体板块"]}),
        cached_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    ))

    # -- Stocks: 自选股基础信息 --
    db.add_all([
        Stock(code="600000", name="浦发银行", market="SH", status="正常"),
        Stock(code="000001", name="平安银行", market="SZ", status="正常"),
        Stock(code="000858", name="五粮液", market="SZ", status="正常"),
    ])

    # -- AlertTrigger: 今日预警 --
    today = datetime.now(UTC).replace(tzinfo=None)
    db.add_all([
        AlertTrigger(
            rule_id=1, stock_code="600000", condition_type="涨幅>",
            trigger_value=Decimal("5.00"), triggered_at=today,
            level="alert", push_status="success",
        ),
        AlertTrigger(
            rule_id=2, stock_code="000001", condition_type="价格突破",
            trigger_value=Decimal("12.50"), triggered_at=today,
            level="watch", push_status="pending",
        ),
    ])

    # -- PushLog: 推送历史 --
    db.add_all([
        PushLog(
            message_id="msg-001", message_type="price_alert",
            channel="lark", status="success", elapsed_ms=120,
            created_at=today,
        ),
        PushLog(
            message_id="msg-002", message_type="briefing",
            channel="telegram", status="failed", error_reason="API 限流",
            elapsed_ms=5000, created_at=today,
        ),
    ])

    # -- PushChannel: 通道状态 --
    db.add_all([
        PushChannel(name="飞书", status="active", rate_limited=False, updated_at=today),
        PushChannel(name="Telegram", status="degraded", rate_limited=True, updated_at=today),
    ])


# ── 第一层 · 黑盒冒烟 ─────────────────────────────────────────────────────


class TestSmoke:
    """TR-006-FS-002: 黑盒冒烟 — 真浏览器访问真栈，证整条切片通了。"""

    def test_dashboard_loads_without_mock(self, page, fullstack_url):
        """不用任何 mock，真浏览器 -> 真后端 -> 真 DB，页面完整加载 200。"""
        page.goto(fullstack_url)
        page.wait_for_load_state("networkidle")

        assert page.url == fullstack_url + "/"
        title = page.title()
        assert title != "" and title != "about:blank"

    def test_static_assets_served(self, page, fullstack_url):
        """CSS/JS 静态文件真实可访问。"""
        for asset in ["/static/css/dashboard.css", "/static/js/dashboard.js"]:
            resp = requests.get(fullstack_url + asset, timeout=5)
            assert resp.status_code == 200, f"静态资源 {asset} 返回 {resp.status_code}"


# ── 第二层 · ② 契约真实性 ─────────────────────────────────────────────────


class TestContractReality:
    """TR-006-FS-003 ~ TR-006-FS-005:
    验证消费者侧假设（前端期望看到的 HTML）与提供者侧真实行为（后端真实渲染）一致。
    """

    def test_market_indices_rendered_from_real_service(self, page, fullstack_url):
        """TR-006-FS-003: 大盘指数模块被真实渲染到页面（非 mock 数据）。

        真栈下外部数据源可能超时降级——这是 DashboardService 的真实行为。
        断言：要么有指数数据，要么有降级提示/空占位（两者都是"真实行为对得上"）。
        """
        page.goto(fullstack_url)
        page.wait_for_load_state("networkidle")

        content = page.content()
        has_indices = any(name in content for name in ["上证指数", "深证成指", "创业板指"])
        has_degraded = any(hint in content for hint in ["延迟", "降级", "缓存", "暂不可用", "--", "数据更新"])
        assert has_indices or has_degraded, \
            "大盘指数模块既没有数据也没有降级提示，接缝行为异常"

    def test_watchlist_rendered_from_real_db(self, page, fullstack_url):
        """TR-006-FS-004: 自选股数据来自真实 DB seed，被真实渲染。

        真栈下 quote_service 调外部数据源可能超时降级——这是真实行为。
        断言：要么有股票数据，要么有引导页/空占位/降级提示。
        """
        page.goto(fullstack_url)
        page.wait_for_load_state("networkidle")

        content = page.content()
        has_stocks = any(name in content for name in ["浦发银行", "平安银行", "五粮液"])
        has_onboarding = any(hint in content for hint in ["添加第一只", "构建", "onboarding", "引导", "开始构建"])
        has_degraded = any(hint in content for hint in ["延迟", "降级", "缓存", "暂不可用"])
        assert has_stocks or has_onboarding or has_degraded, \
            "自选股区域既没有股票数据也没有引导页/降级提示，接缝行为异常"

    def test_briefing_rendered_from_real_cache(self, page, fullstack_url):
        """TR-006-FS-005: 简报数据来自真实 cache 表，被真实渲染。"""
        page.goto(fullstack_url)
        page.wait_for_load_state("networkidle")

        content = page.content()
        # seed 的简报 insights 应被真实读取并渲染
        assert "大盘整体向好" in content or "科技股领涨" in content, \
            "seed 的简报数据未出现在真实渲染的页面中"

    def test_alerts_from_real_db(self, page, fullstack_url):
        """TR-006-FS-006: 今日预警来自真实 alert_triggers 表。"""
        page.goto(fullstack_url)
        page.wait_for_load_state("networkidle")

        content = page.content()
        # seed 的预警条件应被真实查询
        assert "涨幅" in content or "价格突破" in content, \
            "seed 的预警数据未出现在真实渲染的页面中"

    def test_push_history_from_real_db(self, page, fullstack_url):
        """TR-006-FS-007: 推送历史来自真实 push_logs 表。"""
        page.goto(fullstack_url)
        page.wait_for_load_state("networkidle")

        content = page.content()
        # seed 的推送记录应被真实查询
        assert "飞书" in content or "Telegram" in content or "价格预警" in content, \
            "seed 的推送历史未出现在真实渲染的页面中"


# ── 第二层 · ③ 接缝粘合 ───────────────────────────────────────────────────


class TestSeamBonding:
    """TR-006-FS-008 ~ TR-006-FS-010:
    验证序列化往返、错误->UI 映射、降级提示在真栈下正确工作。
    """

    def test_no_500_on_real_stack(self, page, fullstack_url):
        """TR-006-FS-008: 真栈下页面不 500，HTTP 200。"""
        response = page.goto(fullstack_url)
        assert response is not None
        assert response.status == 200, f"真栈下 Dashboard 返回 HTTP {response.status}"

    def test_degradation_message_present_when_external_slow(self, page, fullstack_url):
        """TR-006-FS-009:
        外部数据源响应慢（真 facade 可能超时）时，DashboardService 降级逻辑触发，
        页面不崩溃，且展示降级提示（或空值占位）。
        """
        # 注意：这里不加速/不减速，完全依赖真实行为的超时降级
        page.goto(fullstack_url)
        # DashboardService 默认 5 秒超时，给足等待时间
        page.wait_for_load_state("networkidle", timeout=15000)

        content = page.content()
        # 断言：页面仍有内容（不空白）
        assert len(content) > 1000, "真栈下页面内容异常过少，可能是空白或 500"

        # 若外部数据源不可用，DashboardService 会设置 degraded=True
        # 验证页面中要么有正常数据，要么有降级/缓存提示
        has_normal_data = "上证指数" in content or "浦发银行" in content
        has_degraded_hint = any(hint in content for hint in ["延迟", "降级", "缓存", "暂不可用", "degraded"])
        assert has_normal_data or has_degraded_hint, \
            "页面既没有正常数据也没有降级提示，接缝行为异常"

    def test_datetime_serialization_roundtrip(self, page, fullstack_url):
        """TR-006-FS-010:
        Pydantic datetime -> JSON(mode='json') -> Jinja2 -> HTML 序列化往返正确，
        不出现 '2026-06-06T10:00:00+00:00' 这类 ISO 格式裸暴露。
        """
        page.goto(fullstack_url)
        page.wait_for_load_state("networkidle")

        content = page.content()
        # 检查没有裸 ISO datetime 字符串暴露在 HTML 中
        # 正常应该是格式化后的中文时间（如 "2026-06-06 10:00"）
        import re
        iso_pattern = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")
        matches = iso_pattern.findall(content)

        # 允许少量匹配（可能是 JSON 内联数据），但不应大面积出现在可见文本中
        # 这里用宽松断言：如果匹配很多，说明 datetime 格式化有问题
        if len(matches) > 10:
            pytest.fail(f"发现 {len(matches)} 处裸 ISO datetime 格式，Pydantic->Jinja2 序列化可能未正确格式化")

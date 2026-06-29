"""局部前后端接缝测试 — F8 自然语言设预警真栈对账。

归档信息（testing-system-blueprint）:
- Feature: 010-natural-language-alert
- 缺口来源: test-routing-advisor -> fullstack-slice-testing
- 圈定切片: 浏览器 -> /alerts-page -> nl_alert_input 组件 -> POST /api/alerts/natural-language -> 真 DB
- 命中缺口: ①环境编排(永远) ③接缝粘合 ②契约真实性(不命中,无消费者mock) ④真实时序(不命中,非流式)
- 三层节奏: 慢层（真栈起停 + 真浏览器, 约 30-60s）
- 可追溯 ID: TR-010-FS-001 ~ TR-010-FS-008
"""

import subprocess
import sys
import time
from pathlib import Path

import pytest
import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.database import Base
from backend.app.models.alert_rule import AlertRule


# ── 步骤 1 · 起真栈（Fixture）──────────────────────────────────────────────


@pytest.fixture(scope="session")
def fullstack_url(tmp_path_factory):
    """TR-010-FS-001: 环境编排验证 — 真浏览器 + 真后端 + 真 DB 一键同起、健康检查通过。"""
    db_dir = tmp_path_factory.mktemp("nl_alert_fullstack_db")
    db_path = db_dir / "nl_alert.db"
    db_url = f"sqlite:///{db_path}"

    # 1. 建表
    engine = create_engine(db_url)
    Base.metadata.create_all(bind=engine)
    engine.dispose()

    # 2. 启动 uvicorn（使用测试专用 app，stub 外部股票数据源）
    project_root = str(Path(__file__).resolve().parents[3])
    env = {
        **dict(subprocess.os.environ),
        "DATABASE_URL": db_url,
        "PYTHONPATH": project_root,
        # 确保不调用外部 LLM，完全走规则解析 + 内存 resolver
        "DEEPSEEK_API_KEY": "",
    }
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "backend.tests.e2e.nl_alert_fullstack_app:app",
            "--host",
            "127.0.0.1",
            "--port",
            "0",
        ],
        cwd=project_root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # 3. 从 stderr 读取端口，轮询 HTTP 200
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
        raise RuntimeError("Backend server failed to start for NL alert fullstack slice")

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

    yield {"url": url, "db_url": db_url}

    # 4. Teardown
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture
def db_session(fullstack_url):
    """提供对真栈临时 DB 的直接 ORM 会话，用于验证后端状态。"""
    db_url = fullstack_url["db_url"]
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


# ── 第一层 · 黑盒冒烟 ──────────────────────────────────────────────────────


class TestSmoke:
    """TR-010-FS-002: 黑盒冒烟 — 真浏览器访问真栈，切片整条通。"""

    def test_alerts_page_loads_with_nl_component(self, page, fullstack_url):
        """不用任何 mock，真浏览器 -> 真后端 -> 真 DB，/alerts-page 加载且包含 NL 输入组件。"""
        url = fullstack_url["url"]
        page.goto(f"{url}/alerts-page")
        page.wait_for_load_state("networkidle")

        assert page.url == f"{url}/alerts-page"
        # 组件关键元素存在
        page.locator(".nl-alert-input-component").wait_for(state="visible")
        assert page.locator(".nl-alert-input").is_visible()
        assert page.locator(".nl-alert-submit").is_visible()


# ── 第二层 · ③ 接缝粘合 ───────────────────────────────────────────────────


class TestSeamBonding:
    """TR-010-FS-003 ~ TR-010-FS-008:
    验证序列化往返、错误->UI 映射、候选列表交互在真栈下正确工作。
    """

    def _submit_query(self, page, query: str):
        """在 NL 输入框填入 query 并点击创建预警。"""
        input_el = page.locator(".nl-alert-input")
        input_el.fill(query)
        page.locator(".nl-alert-submit").click()

    def test_empty_input_shows_frontend_validation(self, page, fullstack_url):
        """TR-010-FS-003: 空输入时前端直接提示，不发起后端请求。"""
        page.goto(f"{fullstack_url['url']}/alerts-page")
        page.locator(".nl-alert-input-component").wait_for(state="visible")

        self._submit_query(page, "")

        result = page.locator(".nl-alert-result")
        result.wait_for(state="visible")
        assert "请输入预警条件" in result.text_content()
        assert "text-error" in result.get_attribute("class")

    def test_unsupported_condition_error_renders(self, page, fullstack_url):
        """TR-010-FS-004: 后端返回 unsupported_condition 错误，UI 正确渲染错误文案。"""
        page.goto(f"{fullstack_url['url']}/alerts-page")
        page.locator(".nl-alert-input-component").wait_for(state="visible")

        self._submit_query(page, "成交量超过100万")

        result = page.locator(".nl-alert-result")
        result.wait_for(state="visible")
        text = result.text_content()
        assert "暂不支持成交量条件" in text

    def test_multi_stock_error_renders(self, page, fullstack_url):
        """TR-010-FS-005: 后端返回 multi_stock 错误，UI 正确渲染错误文案。"""
        page.goto(f"{fullstack_url['url']}/alerts-page")
        page.locator(".nl-alert-input-component").wait_for(state="visible")

        self._submit_query(page, "600000和000001跌破10")

        result = page.locator(".nl-alert-result")
        result.wait_for(state="visible")
        assert "一次仅支持一只股票" in result.text_content()

    def test_ambiguity_candidates_click_to_create(self, page, fullstack_url, db_session):
        """TR-010-FS-006: 歧义候选列表真实渲染，点击候选后二次提交并成功创建规则。"""
        page.goto(f"{fullstack_url['url']}/alerts-page")
        page.locator(".nl-alert-input-component").wait_for(state="visible")

        self._submit_query(page, "银行跌破10")

        # 候选列表出现
        candidates = page.locator(".nl-alert-candidates")
        candidates.wait_for(state="visible")
        buttons = candidates.locator("button")
        assert buttons.count() >= 2

        # 点击第一个候选（浦发银行）
        first_candidate = buttons.first
        assert "浦发银行" in first_candidate.text_content()
        first_candidate.click()

        # 等待成功提示
        result = page.locator(".nl-alert-result")
        result.wait_for(state="visible")
        text = result.text_content()
        assert "预警已创建" in text
        assert "600000" in text or "浦发银行" in text
        assert "text-market-up" in result.get_attribute("class")

        # 真 DB 验证规则写入
        rules = db_session.query(AlertRule).filter_by(status="active").all()
        assert any(r.stock_code == "600000" for r in rules)

    def test_success_creates_rule_in_db(self, page, fullstack_url, db_session):
        """TR-010-FS-007: 有效 NL 输入经真后端在真 DB 创建规则，UI 显示成功文案。"""
        page.goto(f"{fullstack_url['url']}/alerts-page")
        page.locator(".nl-alert-input-component").wait_for(state="visible")

        self._submit_query(page, "茅台跌破1500")

        result = page.locator(".nl-alert-result")
        result.wait_for(state="visible")
        text = result.text_content()
        assert "预警已创建" in text
        assert "贵州茅台" in text or "600519" in text

        # 真 DB 验证
        rules = db_session.query(AlertRule).filter_by(status="active").all()
        assert any(r.stock_code == "600519" and r.condition_type == "price_below" for r in rules)

    def test_duplicate_rule_error_renders(self, page, fullstack_url):
        """TR-010-FS-008: 重复创建同一规则，后端返回 duplicate 错误并正确映射到 UI。"""
        page.goto(f"{fullstack_url['url']}/alerts-page")
        page.locator(".nl-alert-input-component").wait_for(state="visible")

        # 第一次提交成功
        self._submit_query(page, "五粮液跌破200")
        result = page.locator(".nl-alert-result")
        result.wait_for(state="visible")
        assert "预警已创建" in result.text_content()

        # 第二次提交同样规则
        self._submit_query(page, "五粮液跌破200")
        result = page.locator(".nl-alert-result")
        result.wait_for(state="visible")
        assert "该预警规则已存在" in result.text_content()

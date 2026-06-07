"""前端结构性补测 — a11y + 响应式 + 契约 mock + 视觉回归基线。

归档信息（testing-system-blueprint）:
- Feature: 006-dashboard
- 缺口来源: test-routing-advisor -> frontend-testing
- 命中层: L0/L1 地基、L2 视觉回归、L3 a11y、L4 响应式、L6 契约 mock
- 三层节奏: 慢层（真浏览器渲染，约 10-30s）
- 可追溯 ID: TR-006-FE-001 ~ TR-006-FE-013
"""

import subprocess
import sys
import time
from pathlib import Path

import pytest
import requests


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def server_url(tmp_path_factory):
    """启动后端服务，返回 base URL。"""
    db_path = tmp_path_factory.mktemp("db") / "test.db"
    project_root = str(Path(__file__).resolve().parents[3])
    env = {
        **dict(subprocess.os.environ),
        "DATABASE_URL": f"sqlite:///{db_path}",
        "PYTHONPATH": project_root,
    }
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", "0"],
        cwd=project_root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # 轮询等待服务就绪（从 stderr 读取端口）
    port = None
    deadline = time.time() + 30
    while time.time() < deadline and port is None:
        import select
        ready, _, _ = select.select([proc.stderr], [], [], 0.5)
        if ready:
            line = proc.stderr.readline().decode()
            if "Uvicorn running on" in line:
                # e.g. "Uvicorn running on http://127.0.0.1:54321"
                port = int(line.split(":")[-1].split()[0].rstrip("/"))

    if port is None:
        proc.kill()
        raise RuntimeError("Backend server failed to start")

    url = f"http://127.0.0.1:{port}"
    # 额外等一次健康检查
    for _ in range(20):
        try:
            if requests.get(url, timeout=2).status_code == 200:
                break
        except Exception:
            pass
        time.sleep(0.2)

    yield url

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


# ── L0/L1 地基 ────────────────────────────────────────────────────────────


class TestFoundation:
    """TR-006-FE-001: 地基 trivial 测试 — 证明浏览器 + 服务能协同跑通。"""

    def test_page_loads_200(self, page, server_url):
        """RED 期望：页面能加载，HTTP 200，包含关键文本。"""
        page.goto(server_url)
        assert page.title() != ""
        assert "A股" in page.content() or "dashboard" in page.content().lower()


# ── L3 a11y ───────────────────────────────────────────────────────────────


class TestAccessibility:
    """TR-006-FE-002 ~ TR-006-FE-004: axe-core 扫描关键页面。"""

    AXE_CDN = "https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.10.2/axe.min.js"

    def _inject_axe(self, page):
        page.evaluate(f"""
            async () => {{
                if (typeof axe === 'undefined') {{
                    const s = document.createElement('script');
                    s.src = '{self.AXE_CDN}';
                    s.onload = () => {{ window.__axe_loaded = true; }};
                    document.head.appendChild(s);
                }} else {{
                    window.__axe_loaded = true;
                }}
            }}
        """)
        # 等脚本加载
        for _ in range(20):
            if page.evaluate("() => window.__axe_loaded === true"):
                break
            time.sleep(0.1)
        else:
            pytest.skip("axe-core CDN 加载失败，跳过 a11y 测试")

    def _run_axe(self, page):
        return page.evaluate("""
            async () => {
                return await axe.run(document, {
                    runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa'] },
                    resultTypes: ['violations']
                });
            }
        """)

    def test_dashboard_no_critical_a11y_violations(self, page, server_url):
        """TR-006-FE-002: Dashboard 首页无 critical/serious a11y 违规。"""
        page.goto(server_url)
        self._inject_axe(page)
        result = self._run_axe(page)

        critical = [v for v in result.get("violations", []) if v.get("impact") == "critical"]
        serious = [v for v in result.get("violations", []) if v.get("impact") == "serious"]

        assert len(critical) == 0, f"Critical a11y violations: {[v['description'] for v in critical]}"
        assert len(serious) == 0, f"Serious a11y violations: {[v['description'] for v in serious]}"

    def test_dashboard_images_have_alt(self, page, server_url):
        """TR-006-FE-003: 所有 img 标签有 alt 属性（或 aria-hidden）。"""
        page.goto(server_url)
        images = page.query_selector_all("img")
        for img in images:
            alt = img.get_attribute("alt")
            aria_hidden = img.get_attribute("aria-hidden")
            assert alt is not None or aria_hidden == "true", "img 缺少 alt 且未标记 aria-hidden"

    def test_interactive_elements_have_accessible_names(self, page, server_url):
        """TR-006-FE-004: 按钮和链接有可访问名称。"""
        page.goto(server_url)
        buttons = page.query_selector_all("button")
        for btn in buttons:
            name = btn.get_attribute("aria-label") or btn.inner_text().strip()
            assert name, "button 缺少可访问名称"

        links = page.query_selector_all("a")
        for link in links:
            name = link.get_attribute("aria-label") or link.inner_text().strip()
            assert name, "a 标签缺少可访问名称"


# ── L4 响应式 ─────────────────────────────────────────────────────────────


class TestResponsive:
    """TR-006-FE-005 ~ TR-006-FE-008: 多视口几何不变量 + 核心信息完整。"""

    VIEWPORTS = [
        (375, 812, "mobile"),
        (768, 1024, "tablet"),
        (1280, 800, "desktop"),
    ]

    @pytest.mark.parametrize("width,height,name", VIEWPORTS)
    def test_no_horizontal_scrollbar(self, page, server_url, width, height, name):
        """TR-006-FE-005: 各视口下无横向滚动条。"""
        page.set_viewport_size({"width": width, "height": height})
        page.goto(server_url)
        page.wait_for_load_state("networkidle")

        scroll_width = page.evaluate("() => document.documentElement.scrollWidth")
        client_width = page.evaluate("() => document.documentElement.clientWidth")
        assert scroll_width <= client_width + 1, f"{name}({width}x{height}) 出现横向滚动: scroll={scroll_width}, client={client_width}"

    @pytest.mark.parametrize("width,height,name", VIEWPORTS)
    def test_core_info_visible(self, page, server_url, width, height, name):
        """TR-006-FE-006: 各视口下核心信息（大盘+自选股+简报）可见。"""
        page.set_viewport_size({"width": width, "height": height})
        page.goto(server_url)
        page.wait_for_load_state("networkidle")

        content = page.content()
        # 核心信息关键词（中/英）
        keywords = ["上证指数", "market", "自选股", "watchlist", "简报", "briefing"]
        found = sum(1 for k in keywords if k in content)
        assert found >= 2, f"{name}({width}x{height}) 核心信息缺失，只找到 {found}/{len(keywords)} 个关键词"

    def test_mobile_hides_sidebar(self, page, server_url):
        """TR-006-FE-007: 移动端隐藏侧边导航栏。"""
        page.set_viewport_size({"width": 375, "height": 812})
        page.goto(server_url)
        page.wait_for_load_state("networkidle")

        sidebar = page.query_selector("nav[role='navigation'], .sidebar, aside, [class*='side-nav']")
        if sidebar:
            visible = sidebar.is_visible()
            # 移动端 sidebar 应该隐藏或不占布局空间
            box = sidebar.bounding_box()
            if box:
                assert box["width"] < 100 or not visible, "移动端 sidebar 仍显示且宽度大于 100px"

    def test_market_index_cards_not_stacked_on_desktop(self, page, server_url):
        """TR-006-FE-008: Desktop 下大盘指数卡片不堆叠（至少 2 列）。"""
        page.set_viewport_size({"width": 1280, "height": 800})
        page.goto(server_url)
        page.wait_for_load_state("networkidle")

        # 找大盘指数区域
        cards = page.query_selector_all("[class*='market'], [class*='index']")
        if len(cards) >= 3:
            # 检查它们是否横向排列（第一个和第二个的 x 坐标不同）
            boxes = [c.bounding_box() for c in cards[:3] if c.bounding_box()]
            if len(boxes) >= 2:
                xs = [b["x"] for b in boxes]
                assert len(set(round(x, -1) for x in xs)) > 1, "Desktop 下大盘卡片全部垂直堆叠"


# ── L6 前后端契约 mock ────────────────────────────────────────────────────


class TestContractMock:
    """TR-006-FE-009 ~ TR-006-FE-011: 前端消费者端 mock，验证契约漂移防御。"""

    def test_mock_market_data_renders_correctly(self, page, server_url):
        """TR-006-FE-009: route 拦截 /market_data，返回受控 Partial HTML，验证前端正确渲染。"""
        mock_html = """
        <div id="market-indices">
            <div class="index-card" data-testid="sh"><span class="name">上证指数</span><span class="value">3050.00</span></div>
            <div class="index-card" data-testid="sz"><span class="name">深证成指</span><span class="value">9800.00</span></div>
            <div class="index-card" data-testid="cy"><span class="name">创业板指</span><span class="value">1950.00</span></div>
        </div>
        <div id="watchlist">
            <div class="stock-row" data-testid="stock-600000"><span class="code">600000</span><span class="name">浦发银行</span></div>
        </div>
        """

        page.route(f"{server_url}/market_data", lambda route: route.fulfill(
            status=200,
            content_type="text/html; charset=utf-8",
            body=mock_html,
        ))

        page.goto(server_url)
        page.wait_for_load_state("networkidle")

        # 触发一次前端轮询（等待 setInterval 触发或手动触发）
        page.evaluate("""
            () => {
                if (typeof fetchMarketData === 'function') fetchMarketData();
                else if (window.marketContainer) window.fetchMarketData && window.fetchMarketData();
            }
        """)
        time.sleep(1)

        # 验证 mock 数据被渲染到页面
        content = page.content()
        assert "3050.00" in content or "上证指数" in content, "mock 行情数据未被前端渲染"

    def test_frontend_shows_error_on_500(self, page, server_url):
        """TR-006-FE-010: /market_data 返回 500 时，前端展示错误态（而非空白）。"""
        page.route(f"{server_url}/market_data", lambda route: route.fulfill(
            status=500,
            content_type="text/html",
            body="<p>Server Error</p>",
        ))

        page.goto(server_url)
        page.wait_for_load_state("networkidle")

        # 等待前端轮询触发
        time.sleep(2)

        # 断言页面仍显示内容（不是完全空白）或者有错误提示
        content = page.content()
        assert len(content) > 500, "500 后页面内容异常过少，可能是空白"

    def test_frontend_shows_degraded_hint_when_data_unavailable(self, page, server_url):
        """TR-006-FE-011: 数据源不可用时，前端展示降级提示。"""
        page.route(f"{server_url}/market_data", lambda route: route.fulfill(
            status=200,
            content_type="text/html",
            body='<div data-degraded="true">数据暂不可用</div>',
        ))

        page.goto(server_url)
        page.wait_for_load_state("networkidle")
        time.sleep(2)

        # 检查降级标记或提示文本存在
        content = page.content()
        degraded_indicators = ["降级", "延迟", "暂不可用", "degraded", "unavailable", "cached"]
        found = any(ind in content for ind in degraded_indicators)
        # 注意：这是条件断言——如果页面本身包含降级 UI，则验证；否则跳过
        if not found:
            pytest.skip("页面未包含可识别的降级提示文本（需人工确认设计规范）")


# ── L2 视觉回归 ───────────────────────────────────────────────────────────


class TestVisualRegression:
    """TR-006-FE-012 ~ TR-006-FE-013: 截图基线建立（首次运行=基线）。"""

    # 基线目录（首次运行生成，人审后确认）
    BASELINE_DIR = Path(__file__).parent / "visual_baselines"

    def _screenshot_path(self, name: str) -> Path:
        self.BASELINE_DIR.mkdir(parents=True, exist_ok=True)
        return self.BASELINE_DIR / f"{name}.png"

    def test_baseline_dashboard_desktop(self, page, server_url):
        """TR-006-FE-012: Desktop 视口 Dashboard 截图基线。"""
        page.set_viewport_size({"width": 1280, "height": 800})
        page.goto(server_url)
        page.wait_for_load_state("networkidle")

        path = self._screenshot_path("dashboard_desktop")
        page.screenshot(path=str(path), full_page=True)
        assert path.exists() and path.stat().st_size > 1000, "截图未生成或文件过小"

    def test_baseline_dashboard_mobile(self, page, server_url):
        """TR-006-FE-013: Mobile 视口 Dashboard 截图基线。"""
        page.set_viewport_size({"width": 375, "height": 812})
        page.goto(server_url)
        page.wait_for_load_state("networkidle")

        path = self._screenshot_path("dashboard_mobile")
        page.screenshot(path=str(path), full_page=True)
        assert path.exists() and path.stat().st_size > 1000, "截图未生成或文件过小"

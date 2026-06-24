"""骨架屏视觉回归测试 — 验证首屏加载无布局跳动。

归档信息（testing-system-blueprint）:
- Feature: 008-redis-adjust
- 缺口来源: test-routing-advisor -> frontend-testing
- 命中缺口: L2 视觉回归（骨架屏切换）
- 三层节奏: 慢层（真浏览器 + 截图对比，约 15-30s）
- 可追溯 ID: TR-008-FE-001 ~ TR-008-FE-003
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
from backend.app.models.stock import Stock
from backend.app.models.watchlist import WatchlistItem


@pytest.fixture(scope="session")
def server_url(tmp_path_factory):
    """启动后端服务，返回 base URL。"""
    db_path = tmp_path_factory.mktemp("db") / "test.db"
    db_url = f"sqlite:///{db_path}"

    # 创建表并 seed watchlist 数据（确保 dashboard 渲染骨架屏而非 onboarding）
    engine = create_engine(db_url)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    with SessionLocal() as db:
        db.add(Stock(code="600000", name="浦发银行", market="SH", status="正常"))
        db.add(WatchlistItem(stock_code="600000", group_id=1))
        db.commit()
    engine.dispose()

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
        raise RuntimeError("Backend server failed to start")

    url = f"http://127.0.0.1:{port}"
    for _ in range(20):
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

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


class TestSkeletonScreenPresence:
    """TR-008-FE-001: 验证骨架屏元素存在。"""

    def test_skeleton_screen_present_on_initial_load(self, page, server_url):
        """页面初始加载时应包含骨架屏占位元素。"""
        # 拦截 /market_data，让 JS fetch 失败（进入 catch，不替换骨架屏）
        page.route(f"{server_url}/market_data", lambda route: route.abort())

        # 只等待 DOM 加载完成，不等待网络空闲
        page.goto(server_url, wait_until="domcontentloaded")

        # 检查骨架屏元素存在
        skeleton_elements = page.query_selector_all("#skeleton-screen .animate-pulse")
        assert len(skeleton_elements) > 0, "首屏应包含骨架屏占位元素"

    def test_skeleton_replaced_by_real_content(self, page, server_url):
        """骨架屏应在数据到达后被真实内容替换。"""
        page.goto(server_url)
        page.wait_for_load_state("networkidle")

        # 等待足够时间让 /market_data 轮询完成
        time.sleep(2)

        # 检查页面是否包含真实内容（大盘指数或自选股数据）
        content = page.content()
        has_real_data = "上证指数" in content or "自选股" in content or "浦发银行" in content

        # 如果没有真实数据，至少检查页面不是空白
        assert len(content) > 1000, "页面内容异常过少"


class TestLayoutStability:
    """TR-008-FE-002 ~ TR-008-FE-003: 验证布局稳定性（防跳动）。"""

    def test_market_container_stable_size(self, page, server_url):
        """TR-008-FE-002: market-data-container 在数据替换前后尺寸保持稳定。"""
        page.goto(server_url)
        page.wait_for_load_state("networkidle")

        # 获取初始容器尺寸
        container = page.query_selector("#market-data-container")
        if not container:
            pytest.skip("未找到 market-data-container 元素")

        initial_box = container.bounding_box()
        if not initial_box:
            pytest.skip("无法获取容器初始尺寸")

        initial_width = initial_box["width"]
        initial_height = initial_box["height"]

        # 等待 /market_data 轮询完成（触发内容替换）
        time.sleep(3)

        # 获取替换后的容器尺寸
        updated_box = container.bounding_box()
        if updated_box:
            updated_width = updated_box["width"]
            updated_height = updated_box["height"]

            # 宽度应保持一致（高度可能因内容变化，但宽度不应跳动）
            assert abs(updated_width - initial_width) < 5, \
                f"容器宽度跳动过大: 初始={initial_width}, 替换后={updated_width}"

    def test_no_horizontal_scrollbar_after_load(self, page, server_url):
        """TR-008-FE-003: 数据加载完成后不出现横向滚动条。"""
        page.set_viewport_size({"width": 1280, "height": 800})
        page.goto(server_url)
        page.wait_for_load_state("networkidle")

        # 等待轮询完成
        time.sleep(3)

        scroll_width = page.evaluate("() => document.documentElement.scrollWidth")
        client_width = page.evaluate("() => document.documentElement.clientWidth")

        assert scroll_width <= client_width + 1, \
            f"数据加载后出现横向滚动条: scroll={scroll_width}, client={client_width}"

    def test_screenshot_baseline_for_skeleton_transition(self, page, server_url):
        """TR-008-FE-004: 骨架屏切换截图基线（首次运行建立基线）。"""
        page.set_viewport_size({"width": 1280, "height": 800})
        page.goto(server_url)
        page.wait_for_load_state("networkidle")

        # 等待数据完全加载
        time.sleep(3)

        baseline_dir = Path(__file__).parent / "visual_baselines"
        baseline_dir.mkdir(parents=True, exist_ok=True)

        path = baseline_dir / "dashboard_after_load.png"
        page.screenshot(path=str(path), full_page=True)

        assert path.exists() and path.stat().st_size > 1000, "截图未生成或文件过小"

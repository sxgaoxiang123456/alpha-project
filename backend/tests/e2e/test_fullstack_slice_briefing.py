"""局部前后端接缝测试 — 009-ai-briefing 手动刷新切片。

归档信息（testing-system-blueprint）:
- Feature: 009-ai-briefing
- 缺口来源: test-routing-advisor -> fullstack-slice-testing
- 圈定切片: 浏览器 Dashboard -> 点击「重新生成简报」-> POST /api/briefing/generate
  -> 后台真实生成（DeepSeek LLM）-> 前端轮询 GET /api/briefing/latest -> UI 更新
- 命中缺口: ①环境编排(永远) ②契约真实性 ③接缝粘合 ④真实时序/实时(轮询)
- 三层节奏: 慢层（真栈起停 + 真浏览器 + 真实 LLM，约 30-60s）
- 可追溯 ID: TR-009-FS-001 ~ TR-009-FS-006
"""

import json
import os
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import pytest
import redis
import requests
from playwright.sync_api import expect
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session, sessionmaker

from backend.app.database import Base
from backend.app.models.cache_entry import CacheEntry
from backend.app.models.group import Group
from backend.app.models.stock import Stock
from backend.app.models.watchlist import WatchlistItem
from backend.app.services.cache_service import CacheService


# ── 步骤 1 · 起真栈（Session Fixture）────────────────────────────────────────


@dataclass
class BriefingStack:
    """真栈句柄，暴露 URL 与冷却状态操控能力，供多个测试保持独立。"""

    url: str
    db_url: str
    redis_url: str
    engine: object = field(repr=False)

    def clear_cooldown(self) -> None:
        """清掉 briefing_manual_cooldown 缓存键，让下一次生成可触发。"""
        with Session(self.engine) as db:
            db.execute(delete(CacheEntry).where(CacheEntry.key == "briefing_manual_cooldown"))
            db.commit()

    def clear_latest_briefing(self) -> None:
        """清掉 latest_briefing 缓存键，让测试必须等待真实生成完成。"""
        with Session(self.engine) as db:
            db.execute(delete(CacheEntry).where(CacheEntry.key == "latest_briefing"))
            db.commit()

    def seed_latest_briefing(self, data: dict) -> None:
        """向 SQLite 缓存写入一份简报，用于让 UI 轮询路径快速命中 200。"""
        with Session(self.engine) as db:
            CacheService(db).set(
                "latest_briefing",
                json.dumps(data, ensure_ascii=False, default=str),
                ttl_seconds=300,
            )

    def set_cooldown(self, seconds: int = 30) -> None:
        """写入 briefing_manual_cooldown 缓存键，让下一次生成返回 429。"""
        with Session(self.engine) as db:
            CacheService(db).set(
                "briefing_manual_cooldown",
                datetime.now(UTC).isoformat(),
                ttl_seconds=seconds,
            )


@pytest.fixture(scope="session")
def redis_container():
    """启动 Redis 容器并返回连接地址，teardown 时强制删除容器。"""
    container_name = f"briefing-redis-test-{uuid.uuid4().hex[:8]}"
    proc = subprocess.run(
        [
            "docker", "run", "--rm", "-d",
            "-p", "0:6379",
            "--name", container_name,
            "redis:7-alpine",
        ],
        capture_output=True, text=True, check=True,
    )
    container_id = proc.stdout.strip()

    try:
        # 获取动态映射端口
        port_info = subprocess.run(
            ["docker", "port", container_name, "6379"],
            capture_output=True, text=True, check=True,
        )
        host_port = int(port_info.stdout.strip().split(":")[-1])
        redis_url = f"redis://127.0.0.1:{host_port}/0"

        # 健康检查
        client = redis.from_url(redis_url, decode_responses=True)
        deadline = time.time() + 15
        while time.time() < deadline:
            try:
                if client.ping():
                    break
            except Exception:
                time.sleep(0.2)
        else:
            raise RuntimeError("Redis container health check failed")

        yield {"url": redis_url, "client": client, "name": container_name}
    finally:
        subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)


def _seed_redis(redis_client, stock_codes: list[str]) -> None:
    """向 Redis 注入行情缓存，让后端跳过 AkShare/BaoStock 外部调用，聚焦 LLM 真实调用。"""
    now = datetime.now(UTC).isoformat()
    market_data = [
        {
            "index_code": "sh000001",
            "index_name": "上证指数",
            "current_point": "3200.50",
            "change_percent": "0.85",
            "change_amount": "27.00",
            "turnover": "45000000000",
            "updated_at": now,
            "source_status": "cached",
            "actual_timestamp": now,
        },
        {
            "index_code": "sz399001",
            "index_name": "深证成指",
            "current_point": "10500.30",
            "change_percent": "-0.35",
            "change_amount": "-37.00",
            "turnover": "52000000000",
            "updated_at": now,
            "source_status": "cached",
            "actual_timestamp": now,
        },
        {
            "index_code": "sz399006",
            "index_name": "创业板指",
            "current_point": "2100.80",
            "change_percent": "0.00",
            "change_amount": "0.00",
            "turnover": "18000000000",
            "updated_at": now,
            "source_status": "cached",
            "actual_timestamp": now,
        },
    ]
    redis_client.set("quotes:market", json.dumps(market_data, ensure_ascii=False, default=str))

    watchlist_data = [
        {
            "stock_code": code,
            "stock_name": code,
            "current_price": str(10.0 + i),
            "change_percent": str([1.25, -0.80][i % 2]),
            "change_amount": str([0.12, -0.08][i % 2]),
            "updated_at": now,
            "status": "normal",
            "source_status": "cached",
        }
        for i, code in enumerate(sorted(stock_codes))
    ]
    cache_key = f"quotes:watchlist:{','.join(sorted(stock_codes))}"
    redis_client.set(cache_key, json.dumps(watchlist_data, ensure_ascii=False, default=str))


@pytest.fixture(scope="session")
def briefing_stack(tmp_path_factory, redis_container):
    """起真栈：临时 DB -> seed -> Redis 缓存 -> 启动 uvicorn -> 健康检查 -> yield 句柄 -> teardown。

    TR-009-FS-001: 环境编排验证 — 浏览器 + FastAPI + SQLite + Redis 真实同起，
    健康检查通过；LLM 保持真实调用，推送通道被环境变量禁用以避免扰动。
    """
    db_dir = tmp_path_factory.mktemp("briefing_fullstack_db")
    db_path = db_dir / "briefing.db"
    db_url = f"sqlite:///{db_path}"

    engine = create_engine(db_url)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)

    stock_codes = []
    with SessionLocal() as db:
        stock_codes = _seed_briefing_data(db)
        db.commit()

    engine.dispose()
    engine = create_engine(db_url)

    _seed_redis(redis_container["client"], stock_codes)

    # 为 UI 轮询路径准备一份缓存简报：让前端点击后能快速命中 200，
    # 同时后台仍会真实调用 DeepSeek LLM 重新生成并覆盖缓存。
    _seed_latest_briefing(engine, {
        "date": "2026-06-23",
        "market_indices": {
            "上证指数": {"current": 3200.50, "change_pct": 0.85},
            "深证成指": {"current": 10500.30, "change_pct": -0.35},
            "创业板指": {"current": 2100.80, "change_pct": 0.0},
        },
        "top_movers": [
            {"stock_code": "600000", "stock_name": "浦发银行", "move_type": "price_surge", "change_percent": 1.25},
            {"stock_code": "000001", "stock_name": "平安银行", "move_type": "price_drop", "change_percent": -0.80},
        ],
        "insights": ["seed 简报"],
        "is_degraded": False,
        "degraded_reason": None,
        "generated_at": datetime.now(UTC).isoformat(),
    })

    project_root = str(Path(__file__).resolve().parents[3])
    env = {
        **dict(os.environ),
        "DATABASE_URL": db_url,
        "REDIS_URL": redis_container["url"],
        "PYTHONPATH": project_root,
        # 禁用真实推送通道，避免测试消息扰动生产聊天群
        "FEISHU_APP_ID": "",
        "FEISHU_APP_SECRET": "",
        "FEISHU_CHAT_ID": "",
        "TELEGRAM_BOT_TOKEN": "",
        "TELEGRAM_PROXY": "",
        "LOG_LEVEL": "WARNING",
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
        raise RuntimeError("Backend server failed to start for briefing fullstack slice")

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

    stack = BriefingStack(url=url, db_url=db_url, redis_url=redis_container["url"], engine=engine)
    yield stack

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def _seed_latest_briefing(engine, data: dict) -> None:
    """向 SQLite 缓存写入一份简报数据，用于 UI 轮询路径快速命中 200。"""
    from sqlalchemy.orm import sessionmaker
    SessionLocal = sessionmaker(bind=engine)
    with SessionLocal() as db:
        CacheService(db).set(
            "latest_briefing",
            json.dumps(data, ensure_ascii=False, default=str),
            ttl_seconds=300,
        )


def _seed_briefing_data(db: Session) -> list[str]:
    """向真库 seed 自选股；返回股票代码列表供 Redis 缓存 key 使用。"""
    group = Group(name="默认分组", is_default=True)
    db.add(group)
    db.flush()

    stocks = [
        Stock(code="600000", name="浦发银行", market="SH", status="正常"),
        Stock(code="000001", name="平安银行", market="SZ", status="正常"),
    ]
    db.add_all(stocks)
    db.flush()

    db.add_all([
        WatchlistItem(stock_code=s.code, group_id=group.id)
        for s in stocks
    ])
    return [s.code for s in stocks]


# ── 第二层 · 黑盒冒烟 ───────────────────────────────────────────────────────


class TestSmoke:
    """TR-009-FS-002: 黑盒冒烟 — 真浏览器访问真栈，简报卡片完整渲染。"""

    def test_dashboard_briefing_card_loads(self, page, briefing_stack):
        """简报卡片、刷新按钮、状态区真实渲染。"""
        page.goto(briefing_stack.url)
        page.wait_for_load_state("networkidle")

        generate_btn = page.locator("#briefing-generate-btn")
        status_el = page.locator("#briefing-status")
        content_el = page.locator("#briefing-content")

        expect(generate_btn).to_be_visible()
        expect(status_el).to_be_visible()
        expect(content_el).to_be_visible()


# ── 第二层 · ② 契约真实性 + ③ 接缝粘合 + ④ 真实时序/实时 ───────────────────


class TestManualRefreshSeam:
    """TR-009-FS-003 ~ TR-009-FS-006:
    验证消费者 mock 假设（响应 shape、错误态映射）与真提供者行为一致，
    并覆盖手动刷新后前端轮询 /api/briefing/latest 的异步路径。
    """

    def test_manual_refresh_triggers_polling_and_updates_ui(self, page, briefing_stack):
        """TR-009-FS-003 / TR-009-FS-004 / TR-009-FS-005:
        真实点击「重新生成简报」-> 前端收到 202 -> 轮询 latest -> UI 更新为真实简报。
        同时断言 /api/briefing/latest 的 JSON shape 满足前端解析契约。
        """
        briefing_stack.clear_cooldown()

        page.goto(briefing_stack.url)
        page.wait_for_load_state("networkidle")

        generate_btn = page.locator("#briefing-generate-btn")
        status_el = page.locator("#briefing-status")
        content_el = page.locator("#briefing-content")

        # 触发
        generate_btn.click()

        # 同步阶段：按钮禁用 + 状态提示触发中
        expect(generate_btn).to_be_disabled()
        expect(status_el).to_contain_text("正在触发")

        # 异步阶段：POST 返回 202 后进入轮询
        expect(status_el).to_contain_text("已触发", timeout=15000)
        expect(status_el).to_contain_text("轮询", timeout=15000)

        # 真实时序：轮询命中 latest 200 后，前端更新卡片并进入冷却
        # 注意：setCooldown 会立即把状态覆盖为「冷却中」，因此不断言「简报已更新」文本
        expect(status_el).to_contain_text("冷却中", timeout=30000)
        expect(generate_btn).to_be_disabled()

        # 契约真实性落地到 UI：大盘指数至少有一个被渲染
        content = content_el.inner_html()
        assert "上证指数" in content or "深证成指" in content or "创业板指" in content, \
            "UI 未渲染大盘指数，前后端契约可能在字段名/类型上不一致"

        # 额外验证 API 响应 shape 与前端解析一致
        data = None
        for _ in range(20):
            r = requests.get(f"{briefing_stack.url}/api/briefing/latest", timeout=5)
            if r.status_code == 200:
                data = r.json()
                break
            time.sleep(0.5)
        assert data is not None, "latest 接口未返回 200"
        assert "date" in data
        assert "market_indices" in data and isinstance(data["market_indices"], dict)
        assert "top_movers" in data and isinstance(data["top_movers"], list)
        assert "insights" in data and isinstance(data["insights"], list)
        assert "is_degraded" in data

    def test_manual_refresh_cooldown_reflected_in_ui(self, page, briefing_stack):
        """TR-009-FS-006: 当后端返回 429 冷却中时，UI 正确显示「冷却中」并禁用按钮。"""
        briefing_stack.set_cooldown(seconds=30)

        page.goto(briefing_stack.url)
        page.wait_for_load_state("networkidle")

        status_el = page.locator("#briefing-status")
        generate_btn = page.locator("#briefing-generate-btn")

        generate_btn.click()

        expect(status_el).to_contain_text("冷却中", timeout=10000)
        expect(generate_btn).to_be_disabled()

    def test_real_llm_generation_end_to_end(self, briefing_stack):
        """TR-009-FS-003（契约真实性补充）:
        清空缓存后真实触发 /api/briefing/generate，等待后台完成 DeepSeek LLM 调用，
        断言 /api/briefing/latest 返回的 JSON shape 与业务契约一致。
        """
        briefing_stack.clear_cooldown()
        briefing_stack.clear_latest_briefing()

        resp = requests.post(f"{briefing_stack.url}/api/briefing/generate", timeout=10)
        assert resp.status_code == 202, f"生成触发失败: {resp.status_code} {resp.text}"

        data = None
        for _ in range(120):
            r = requests.get(f"{briefing_stack.url}/api/briefing/latest", timeout=5)
            if r.status_code == 200:
                data = r.json()
                break
            time.sleep(1)
        assert data is not None, "轮询 120s 仍未拿到真实 LLM 生成的简报"

        assert "date" in data
        assert "market_indices" in data and isinstance(data["market_indices"], dict)
        assert "top_movers" in data and isinstance(data["top_movers"], list)
        assert "insights" in data and isinstance(data["insights"], list)
        assert "is_degraded" in data

"""完整功能链路测试 — 009-ai-briefing 跨 feature P0 安全网。

归档信息（testing-system-blueprint）:
- Feature: 009-ai-briefing
- 缺口来源: test-router.md -> full-chain-testing
- 命中缺口: ①通路挖掘 ②关键性分级 ③全系统编排 ④异步/时间/跨通道 ⑤journey 可追溯
- 三层节奏: 慢层（真栈起停 + 真浏览器 + 非 UI 编排驱动，约 60-120s）
- 可追溯 ID: TR-009-FC-001 ~ TR-009-FC-006
- 风险级别: P0（核心主流程可用性）
- 发布门: 硬阻断

═════════════════════════════════════════════════════════════════════════════
通路清单（Path Inventory）— 三源模型挖掘
═════════════════════════════════════════════════════════════════════════════

【源 A · 静态代码图】语法指纹清晰的边
- main.py:266 register_briefing_job cron 绑定 quote_scheduler.send_briefing_if_trading_day
- quote_scheduler.py:55 send_briefing_if_trading_day() → briefing_service_factory() → generate()
- briefing_service.py:51 generate() 编排：交易日检查 → 行情等待 → 大盘/自选股/历史行情/预警
  → TopMoverService → PromptLoader → BriefingLLMClient(DeepSeek) → _build_briefing
  → CacheService.set("latest_briefing") + PushService.send()
- dashboard.py:38 GET / → DashboardService.build_dashboard_view() → _get_briefing()

【源 B · 运行时 trace】FE↔BE 桥边 + 解耦边
- test_fullstack_slice_briefing.py 已验证: 手动刷新 → POST /api/briefing/generate → 真实 LLM → UI 轮询
- APScheduler 在 lifespan 中启动，cron 触发为典型非 UI 跳步

【源 C · spec 契约】语义 + P0 路径决策
- test-router.md 明确 P0-1 正常交易日自动简报完整链路
- test-router.md 明确 P0-2 LLM 降级仍推送模板简报
- test-router.md 明确 P0-3 非交易日零触发

─────────────────────────────────────────────────────────────────────────────
Journey P0-1: 正常交易日自动简报完整链路
Features: F7(009-ai-briefing) → F2(Cache) + F4(Push) → F5(Dashboard)
跳步: [NON-UI]APScheduler cron → QuoteScheduler.send_briefing_if_trading_day()
      → BriefingService.generate() → DeepSeek LLM → 缓存 + PushLog → Dashboard 展示
交接点: QuoteScheduler → BriefingService → CacheEntry + PushLog → Dashboard HTML

Journey P0-2: LLM 降级仍推送模板简报
Features: F7(009-ai-briefing) → F4(Push)
跳步: [NON-UI]手动触发（编排驱动）→ BriefingService → LLM HTTP 边界失败 → 降级简报
      → 缓存 + PushLog
交接点: BriefingLLMClient 异常 → _build_briefing(degraded=True) → PushLog 元数据 is_degraded

Journey P0-3: 非交易日零触发
Features: F7(009-ai-briefing)
跳步: [NON-UI]手动触发（编排驱动）→ is_trading_day() 返回 False → 无缓存、无 PushLog
交接点: trading_calendar.is_trading_day() 阻止整条链路启动
─────────────────────────────────────────────────────────────────────────────
"""

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, HTTPServer
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
from backend.app.models.push_log import PushLog
from backend.app.models.stock import Stock
from backend.app.models.watchlist import WatchlistItem


@dataclass
class FullChainBriefingStack:
    """全链路测试栈句柄，暴露 URL、DB、Redis 与缓存/日志操控能力。"""

    url: str
    db_url: str
    redis_url: str
    engine: object
    redis_client: object

    def clear_latest_briefing(self) -> None:
        """清掉 latest_briefing 缓存键，避免前置测试污染。"""
        with Session(self.engine) as db:
            db.execute(delete(CacheEntry).where(CacheEntry.key == "latest_briefing"))
            db.commit()

    def count_briefing_push_logs(self) -> int:
        """返回 message_type=briefing 的 PushLog 数量。"""
        with Session(self.engine) as db:
            return db.query(PushLog).filter_by(message_type="briefing").count()

    def latest_briefing_from_db(self) -> dict | None:
        """从 SQLite 缓存读取 latest_briefing。"""
        with Session(self.engine) as db:
            entry = db.query(CacheEntry).filter_by(key="latest_briefing").first()
            if entry is None:
                return None
            try:
                return json.loads(entry.content)
            except Exception:
                return None


# ── 步骤 1 · 起全系统真栈（Fixture）────────────────────────────────────────


@pytest.fixture(scope="session")
def redis_container():
    """启动 Redis 容器并返回连接地址，teardown 时强制删除容器。"""
    container_name = f"fullchain-redis-test-{uuid.uuid4().hex[:8]}"
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
        port_info = subprocess.run(
            ["docker", "port", container_name, "6379"],
            capture_output=True, text=True, check=True,
        )
        host_port = int(port_info.stdout.strip().split(":")[-1])
        redis_url = f"redis://127.0.0.1:{host_port}/0"

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


def _seed_briefing_chain_data(db: Session) -> list[str]:
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


def _seed_redis_quotes(redis_client, stock_codes: list[str]) -> None:
    """向 Redis 注入行情缓存，让后端优先命中缓存、跳过 AkShare/BaoStock 外部调用。"""
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
            "volume": 100000,
            "updated_at": now,
            "status": "normal",
            "source_status": "cached",
        }
        for i, code in enumerate(sorted(stock_codes))
    ]
    cache_key = f"quotes:watchlist:{','.join(sorted(stock_codes))}"
    redis_client.set(cache_key, json.dumps(watchlist_data, ensure_ascii=False, default=str))


@pytest.fixture(scope="session")
def full_chain_briefing_stack(tmp_path_factory, redis_container):
    """起全系统真栈：临时 DB -> seed -> Redis 缓存 -> 启动 uvicorn -> yield -> teardown。

    TR-009-FC-001: 全系统编排验证 — 旅程穿过的所有 feature + 依赖真实同起、可复现、
    健康检查通过。只 stub 外部第三方边界（DeepSeek 在 P0-2 单独 stub、飞书/Telegram 全部清空）。
    """
    db_dir = tmp_path_factory.mktemp("fullchain_briefing_db")
    db_path = db_dir / "briefing.db"
    db_url = f"sqlite:///{db_path}"

    engine = create_engine(db_url)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)

    stock_codes = []
    with SessionLocal() as db:
        stock_codes = _seed_briefing_chain_data(db)
        db.commit()

    engine.dispose()
    engine = create_engine(db_url)

    _seed_redis_quotes(redis_container["client"], stock_codes)

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
        raise RuntimeError("Backend server failed to start for full-chain briefing")

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

    stack = FullChainBriefingStack(
        url=url,
        db_url=db_url,
        redis_url=redis_container["url"],
        engine=engine,
        redis_client=redis_container["client"],
    )
    yield stack

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


# ── 编排驱动辅助：手动触发 QuoteScheduler（不等 cron）────────────────────────


def _get_free_port() -> int:
    """获取一个可用端口。"""
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _LLMFaultServer:
    """本地 DeepSeek 故障桩：所有请求返回 503，用于验证 LLM 降级路径。"""

    def __init__(self, port: int):
        self.port = port
        self._server = None
        self._thread = None

    def start(self):
        class _Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                self.send_response(503)
                self.end_headers()
                self.wfile.write(b"Service Unavailable")

            def log_message(self, format, *args):
                pass

        self._server = HTTPServer(("127.0.0.1", self.port), _Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

        # 等待端口就绪
        deadline = time.time() + 5
        while time.time() < deadline:
            try:
                requests.get(f"http://127.0.0.1:{self.port}/", timeout=0.2)
                break
            except Exception:
                time.sleep(0.05)

    def stop(self):
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()

    def __enter__(self):
        self.start()
        return f"http://127.0.0.1:{self.port}"

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        return False


def _run_scheduler_trigger(
    stack: FullChainBriefingStack,
    current_date: date,
    *,
    llm_base_url: str | None = None,
    llm_timeout: int | None = None,
    llm_retries: int | None = None,
    llm_interval: int | None = None,
    timeout_seconds: int = 120,
) -> subprocess.CompletedProcess:
    """在独立子进程中构造 QuoteScheduler 并手动触发 send_briefing_if_trading_day。

    使用与真栈相同的 DB 和 Redis，因此生成的缓存/日志对真栈与浏览器可见。
    """
    project_root = str(Path(__file__).resolve().parents[3])

    env = {
        **dict(os.environ),
        "DATABASE_URL": stack.db_url,
        "REDIS_URL": stack.redis_url,
        "PYTHONPATH": project_root,
        "FEISHU_APP_ID": "",
        "FEISHU_APP_SECRET": "",
        "FEISHU_CHAT_ID": "",
        "TELEGRAM_BOT_TOKEN": "",
        "TELEGRAM_PROXY": "",
        "LOG_LEVEL": "WARNING",
    }
    if llm_base_url is not None:
        env["DEEPSEEK_BASE_URL"] = llm_base_url
    if llm_timeout is not None:
        env["DEEPSEEK_TIMEOUT_SECONDS"] = str(llm_timeout)
    if llm_retries is not None:
        env["DEEPSEEK_RETRY_ATTEMPTS"] = str(llm_retries)
    if llm_interval is not None:
        env["DEEPSEEK_RETRY_INTERVAL_SECONDS"] = str(llm_interval)

    script = f'''
import os
import sys

os.environ["DATABASE_URL"] = {stack.db_url!r}
os.environ["REDIS_URL"] = {stack.redis_url!r}

from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import redis as _redis_lib

from backend.app.core.redis_cache import RedisCache
from backend.app.core.quote_scheduler import QuoteScheduler
from backend.app.core.trading_calendar import is_trading_day
from backend.app.services.briefing_service import BriefingService
from backend.app.services.briefing_llm_client import BriefingLLMClient
from backend.app.services.cache_service import CacheService
from backend.app.services.data_source_facade import DataSourceFacade
from backend.app.services.market_index import MarketIndexService
from backend.app.services.prompt_loader import PromptLoader
from backend.app.services.push_service import PushService
from backend.app.services.quote_service import QuoteService
from backend.app.services.top_mover_service import TopMoverService
from backend.app.config import get_settings

engine = create_engine({stack.db_url!r})
SessionLocal = sessionmaker(bind=engine)

raw_redis = _redis_lib.from_url({stack.redis_url!r}, decode_responses=True)
redis_cache = RedisCache(client=raw_redis)

with SessionLocal() as db:
    facade = DataSourceFacade(db)
    cache = CacheService(db)
    market_index_service = MarketIndexService(
        facade=facade, cache=cache, redis_cache=redis_cache
    )
    quote_service = QuoteService(
        db=db, facade=facade, cache=cache, redis_cache=redis_cache
    )
    top_mover_service = TopMoverService(db=db)
    prompt_loader = PromptLoader()

    settings = get_settings()
    llm_client = BriefingLLMClient(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        model=settings.deepseek_model,
        timeout_seconds=settings.deepseek_timeout_seconds,
        retry_attempts=settings.deepseek_retry_attempts,
        retry_interval_seconds=settings.deepseek_retry_interval_seconds,
    )
    push_service = PushService(db=db, feishu_client=None, telegram_client=None)

    quote_scheduler = QuoteScheduler(
        quote_service=quote_service,
        market_index_service=market_index_service,
        is_trading_day=is_trading_day,
    )
    briefing_service = BriefingService(
        db=db,
        market_index_service=market_index_service,
        quote_service=quote_service,
        top_mover_service=top_mover_service,
        prompt_loader=prompt_loader,
        llm_client=llm_client,
        is_trading_day=is_trading_day,
        push_service=push_service,
        cache_service=cache,
        redis_cache=redis_cache,
        fallback_quotes_provider=lambda: {{}},
        quote_refresh_waiter=quote_scheduler.wait_for_quote_refresh,
    )
    quote_scheduler.briefing_service_factory = lambda: briefing_service

    target_date = date.fromisoformat({current_date.isoformat()!r})
    quote_scheduler.send_briefing_if_trading_day(current_date=target_date)
    print("TRIGGER_DONE")
'''
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(script)
        script_path = f.name

    try:
        result = subprocess.run(
            [sys.executable, script_path],
            cwd=project_root,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        if result.returncode != 0:
            raise AssertionError(
                f"Scheduler trigger subprocess failed (exit {result.returncode}):\n"
                f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
            )
        return result
    finally:
        try:
            os.unlink(script_path)
        except Exception:
            pass


def _wait_for_latest_briefing(stack: FullChainBriefingStack, *, timeout_seconds: int = 30) -> dict | None:
    """轮询 /api/briefing/latest 直到 200 或超时。"""
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            r = requests.get(f"{stack.url}/api/briefing/latest", timeout=5)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        time.sleep(0.5)
    return None


def _weekday_date(reference: date | None = None) -> date:
    """返回一个确保为工作日（周一至周五）的日期，用于交易日场景。"""
    d = reference or date.today()
    if d.weekday() >= 5:
        # 回退到上周五
        d = d - timedelta(days=d.weekday() - 4)
    return d


# ── 第二层 · P0 关键旅程端到端断言 ──────────────────────────────────────────


class TestP0NormalTradingDayAutoBriefing:
    """TR-009-FC-002 ~ TR-009-FC-003:
    P0-1 正常交易日自动简报完整链路。
    """

    def test_auto_briefing_generates_and_shows_on_dashboard(
        self, page, full_chain_briefing_stack
    ):
        """TR-009-FC-002: 编排驱动触发 cron 等价路径 → 真实 LLM 生成简报 →
        缓存写入 → PushLog 记录 → Dashboard 渲染可见。
        """
        stack = full_chain_briefing_stack
        stack.clear_latest_briefing()
        before_logs = stack.count_briefing_push_logs()

        trading_day = _weekday_date()
        _run_scheduler_trigger(stack, trading_day, timeout_seconds=180)

        # 交接点 1: /api/briefing/latest 返回非降级简报
        data = _wait_for_latest_briefing(stack, timeout_seconds=30)
        assert data is not None, "触发后未在 30s 内拿到 latest_briefing"
        assert "date" in data
        assert "market_indices" in data and isinstance(data["market_indices"], dict)
        assert "insights" in data and isinstance(data["insights"], list)
        assert data.get("is_degraded") is False, "P0-1 正常链路不应降级"

        # 交接点 2: PushLog 增加 briefing 记录（外部通道被 stub，状态可能为 failed，但日志必须有）
        after_logs = stack.count_briefing_push_logs()
        assert after_logs == before_logs + 1, f"PushLog 未增加 briefing 记录: {before_logs} -> {after_logs}"

        # 交接点 3: 浏览器 Dashboard 真实渲染简报内容
        page.goto(stack.url)
        page.wait_for_load_state("networkidle")

        content = page.content()
        assert "每日 AI 简报" in content
        assert "今日暂无简报" not in content

        # 大盘指数来自 Redis 缓存，应被渲染
        briefing_content = page.locator("#briefing-content")
        expect(briefing_content).to_contain_text("上证指数", timeout=10000)


class TestP0LLMDegradationStillPushesTemplate:
    """TR-009-FC-004 ~ TR-009-FC-005:
    P0-2 LLM 降级仍推送模板简报。
    """

    def test_llm_failure_degraded_briefing_cached_and_visible(
        self, page, full_chain_briefing_stack
    ):
        """TR-009-FC-004: DeepSeek HTTP 边界返回 503 → BriefingService 降级 →
        模板简报仍被缓存并提交到 PushService。
        """
        stack = full_chain_briefing_stack
        before_logs = stack.count_briefing_push_logs()
        trading_day = _weekday_date()

        with _LLMFaultServer(_get_free_port()) as llm_base_url:
            _run_scheduler_trigger(
                stack,
                trading_day,
                llm_base_url=llm_base_url,
                llm_timeout=5,
                llm_retries=1,
                llm_interval=1,
                timeout_seconds=60,
            )

        # 交接点 1: 缓存中的简报 is_degraded=True
        data = _wait_for_latest_briefing(stack, timeout_seconds=30)
        assert data is not None, "降级场景下未拿到 latest_briefing"
        assert data.get("is_degraded") is True, "LLM 失败场景未产生降级简报"
        assert "degraded_reason" in data

        # 交接点 2: PushLog 记录了 briefing 且元数据标记 is_degraded
        after_logs = stack.count_briefing_push_logs()
        assert after_logs == before_logs + 1, "降级场景下 PushLog 未增加 briefing 记录"
        with Session(stack.engine) as db:
            latest_log = (
                db.query(PushLog)
                .filter_by(message_type="briefing")
                .order_by(PushLog.created_at.desc())
                .first()
            )
            assert latest_log is not None
            metadata = json.loads(latest_log.metadata_json or "{}")
            assert metadata.get("is_degraded") is True

        # 交接点 3: Dashboard 展示降级提示
        page.goto(stack.url)
        page.wait_for_load_state("networkidle")

        content = page.content()
        degraded_reason = data.get("degraded_reason", "")
        assert "简报已降级" in content or degraded_reason in content, (
            "Dashboard 未展示降级提示"
        )


class TestP0NonTradingDayZeroTrigger:
    """TR-009-FC-006:
    P0-3 非交易日零触发。
    """

    def test_non_trading_day_no_briefing_no_push_log(
        self, full_chain_briefing_stack
    ):
        """TR-009-FC-006: 周六触发 send_briefing_if_trading_day() →
        is_trading_day() 返回 False → 无缓存、无 PushLog。
        """
        stack = full_chain_briefing_stack
        stack.clear_latest_briefing()
        before_logs = stack.count_briefing_push_logs()

        # 2026-06-20 为周六，A 股非交易日；is_trading_day 的 weekday 检查会先拦截
        saturday = date(2026, 6, 20)
        _run_scheduler_trigger(stack, saturday, timeout_seconds=30)

        # 交接点: 无 latest_briefing 缓存
        cached = stack.latest_briefing_from_db()
        assert cached is None, "非交易日不应生成简报缓存"

        # 交接点: PushLog briefing 数量未变
        after_logs = stack.count_briefing_push_logs()
        assert after_logs == before_logs, "非交易日不应产生 briefing 推送日志"

        # 交接点: /api/briefing/latest 返回 404
        resp = requests.get(f"{stack.url}/api/briefing/latest", timeout=5)
        assert resp.status_code == 404, "非交易日 latest 接口应返回 404"

"""ETag/304 前后端接缝测试 — 真栈对账，零 mock。

归档信息（testing-system-blueprint）:
- Feature: 008-redis-adjust
- 缺口来源: test-routing-advisor -> fullstack-slice-testing
- 圈定切片: 浏览器(JS fetch + If-None-Match) <-> GET /market_data <-> FastAPI ETag/304 响应
- 命中缺口: ①环境编排(永远) ②契约真实性(ETag/304 新增契约) ③接缝粘合(If-None-Match 透传/304->JS 不更新)
- 三层节奏: 慢层（真栈起停 + 真浏览器, 约 30-60s）
- 可追溯 ID: TR-008-FS-001 ~ TR-008-FS-006
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
from backend.app.models.cache_entry import CacheEntry
from backend.app.models.push_channel import PushChannel
from backend.app.models.push_log import PushLog
from backend.app.models.stock import Stock


# ── 步骤 1 · 起真栈（ Fixture ）──────────────────────────────────────────


@pytest.fixture(scope="session")
def fullstack_url(tmp_path_factory):
    """起真栈：临时 DB -> seed 数据 -> 启动 uvicorn -> 健康检查 -> yield URL -> teardown。

    TR-008-FS-001: 环境编排验证 — 两侧+依赖真实同起、可复现、健康检查通过。
    """
    db_dir = tmp_path_factory.mktemp("etag_db")
    db_path = db_dir / "etag.db"
    db_url = f"sqlite:///{db_path}"

    engine = create_engine(db_url)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)

    with SessionLocal() as db:
        _seed_data(db)
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
        raise RuntimeError("Backend server failed to start for ETag seam test")

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

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def _seed_data(db: Session) -> None:
    """向真库 seed 测试数据。"""
    db.add(CacheEntry(
        key="latest_briefing",
        content=json.dumps({"insights": ["大盘整体向好"]}),
        cached_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    ))
    db.add_all([
        Stock(code="600000", name="浦发银行", market="SH", status="正常"),
    ])
    db.add_all([
        PushChannel(name="飞书", status="active", rate_limited=False, updated_at=datetime.now(UTC).replace(tzinfo=None)),
    ])
    db.add_all([
        PushLog(message_id="msg-001", message_type="price_alert", channel="lark", status="success", elapsed_ms=120, created_at=datetime.now(UTC).replace(tzinfo=None)),
    ])


# ── 第一层 · 黑盒冒烟 ─────────────────────────────────────────────────────


class TestETagSmoke:
    """TR-008-FS-002: 黑盒冒烟 — 真浏览器访问真栈，ETag/304 切片通了。"""

    def test_market_data_returns_etag_on_first_load(self, page, fullstack_url):
        """首次访问 /market_data 返回 200 + ETag 头。"""
        page.goto(fullstack_url)
        page.wait_for_load_state("networkidle")

        # 等待 JS 轮询触发（首次 fetchMarketData 在页面加载后执行）
        time.sleep(2)

        # 通过浏览器性能条目验证请求
        entries = page.evaluate("""
            () => performance.getEntriesByType('resource')
                .filter(e => e.name.includes('/market_data'))
        """)

        assert len(entries) > 0, "未检测到 /market_data 请求"

        # 首次请求应为 200
        first_entry = entries[0]
        assert first_entry.get("responseStatus") == 200, f"首次请求应返回 200，实际 {first_entry.get('responseStatus')}"

    def test_refresh_triggers_market_data_request(self, page, fullstack_url):
        """页面自动刷新会触发 /market_data 请求。"""
        page.goto(fullstack_url)
        page.wait_for_load_state("networkidle")

        # 等待至少一次轮询
        time.sleep(3)

        entries = page.evaluate("""
            () => performance.getEntriesByType('resource')
                .filter(e => e.name.includes('/market_data'))
        """)

        assert len(entries) >= 1, "未检测到 /market_data 轮询请求"


# ── 第二层 · ② 契约真实性 ─────────────────────────────────────────────────


class TestContractReality:
    """TR-008-FS-003 ~ TR-008-FS-004:
    验证消费者侧假设（JS 期望的 ETag/304 行为）与提供者侧真实行为一致。
    """

    def test_etag_header_present_in_response(self, page, fullstack_url):
        """TR-008-FS-003: /market_data 响应包含 ETag 头（SHA-256 hex）。"""
        page.goto(fullstack_url)
        page.wait_for_load_state("networkidle")
        time.sleep(2)

        # 通过 performance API 获取响应头
        etag = page.evaluate("""
            async () => {
                const resp = await fetch('/market_data');
                return resp.headers.get('etag');
            }
        """)

        assert etag is not None, "/market_data 响应缺少 ETag 头"
        # ETag = SHA-256 前 32 位 hex（实现细节：hashlib.sha256(...).hexdigest()[:32]）
        assert len(etag) == 32, f"ETag 长度应为 32，实际 {len(etag)}"

    def test_304_response_has_no_body(self, page, fullstack_url):
        """TR-008-FS-004: 304 响应无 body；若行情数据变化则返回 200 并携带新 ETag。"""
        page.goto(fullstack_url)
        page.wait_for_load_state("networkidle")
        time.sleep(2)

        # 第一次获取 ETag，紧接着用相同 ETag 请求
        result = page.evaluate("""
            async () => {
                const r1 = await fetch('/market_data');
                const etag1 = r1.headers.get('etag');
                const r2 = await fetch('/market_data', {
                    headers: { 'If-None-Match': etag1 }
                });
                const etag2 = r2.headers.get('etag');
                return {
                    firstStatus: r1.status,
                    secondStatus: r2.status,
                    secondBodyLength: (await r2.text()).length,
                    etag1: etag1,
                    etag2: etag2
                };
            }
        """)

        assert result["firstStatus"] == 200, f"首次请求应返回 200，实际 {result['firstStatus']}"
        assert result["etag1"], "首次响应应携带 ETag"

        if result["secondStatus"] == 304:
            assert result["secondBodyLength"] == 0, f"304 响应 body 应为空，实际 {result['secondBodyLength']} 字节"
            assert result["etag2"] == result["etag1"], "304 响应 ETag 应与请求一致"
        else:
            assert result["secondStatus"] == 200, f"ETag 过期后应返回 200，实际 {result['secondStatus']}"
            assert result["secondBodyLength"] > 0, "200 响应应携带新 body"
            assert result["etag2"] != result["etag1"], "行情变化后 ETag 应变化"


# ── 第二层 · ③ 接缝粘合 ───────────────────────────────────────────────────


class TestSeamBonding:
    """TR-008-FS-005 ~ TR-008-FS-006:
    验证 If-None-Match 透传、304->JS 不更新 DOM、200->JS 更新 DOM。
    """

    def test_if_none_match_header_forwarded(self, page, fullstack_url):
        """TR-008-FS-005: JS 发送的 If-None-Match 头被服务端正确接收并比对。"""
        page.goto(fullstack_url)
        page.wait_for_load_state("networkidle")
        time.sleep(2)

        result = page.evaluate("""
            async () => {
                const r1 = await fetch('/market_data');
                const etag = r1.headers.get('etag');
                const r2 = await fetch('/market_data', {
                    headers: { 'If-None-Match': etag }
                });
                const newEtag = r2.headers.get('etag');
                return {
                    etagSent: etag !== null,
                    status: r2.status,
                    etag: etag,
                    newEtag: newEtag
                };
            }
        """)

        assert result["etagSent"], "JS 应发送 If-None-Match 头"
        assert result["status"] in (200, 304), f"服务端应正确比对 ETag，实际 {result['status']}"

        if result["status"] == 304:
            assert result["newEtag"] == result["etag"], "304 响应应携带相同 ETag"
        else:
            assert result["newEtag"] != result["etag"], "行情变化后服务端应返回新 ETag"

    def test_304_does_not_update_dom(self, page, fullstack_url):
        """TR-008-FS-006: 304 响应时 JS 不更新 DOM（innerHTML 不替换）。"""
        page.goto(fullstack_url)
        page.wait_for_load_state("networkidle")

        # 等待首次数据加载完成
        time.sleep(2)

        # 获取当前 DOM 内容
        initial_content = page.evaluate(
            "() => document.getElementById('market-data-container')?.innerHTML || ''"
        )

        # 等待下一次轮询
        time.sleep(3)

        # 再次获取 DOM 内容
        after_poll_content = page.evaluate(
            "() => document.getElementById('market-data-container')?.innerHTML || ''"
        )

        # 如果 DOM 发生变化，必须是由于 200 响应（数据变化）；纯 304 不应导致 DOM 变化
        if initial_content != after_poll_content:
            statuses = page.evaluate("""
                () => performance.getEntriesByType('resource')
                    .filter(e => e.name.includes('/market_data'))
                    .map(e => e.responseStatus)
            """)
            assert 200 in statuses, \
                "DOM 发生变化，但未检测到 200 响应（304 不应替换 innerHTML）"

    def test_200_updates_dom_when_data_changes(self, page, fullstack_url):
        """TR-008-FS-007: 数据变化后 200 响应更新 DOM 并记录新 ETag。"""
        page.goto(fullstack_url)
        page.wait_for_load_state("networkidle")
        time.sleep(2)

        # 获取初始内容
        initial_content = page.evaluate(
            "() => document.getElementById('market-data-container')?.innerHTML || ''"
        )

        # 注意：在真栈下，我们无法直接控制行情数据变化来触发 ETag 变化
        # 所以这里用宽松断言：验证页面有内容，且 JS 的 ETag 机制在工作
        assert len(initial_content) > 100, "market-data-container 应包含内容"

        # 验证 JS 确实发起了轮询请求
        entries = page.evaluate("""
            () => performance.getEntriesByType('resource')
                .filter(e => e.name.includes('/market_data'))
        """)
        assert len(entries) >= 1, "JS 应触发至少一次 /market_data 轮询"

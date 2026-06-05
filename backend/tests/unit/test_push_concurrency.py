"""PushService 并发竞态测试。

覆盖 test-routing-advisor 标出的结构性缺口：
- 并发发送时 _record_channel_failure 的丢失更新（read-modify-write 竞态）
- 并发创建 PushChannel 记录的主键冲突安全

栈: Python + SQLAlchemy 2.0 + SQLite (check_same_thread=False)
工具: concurrent.futures.ThreadPoolExecutor (标准库)

参考: test_concurrency.py (CircuitBreaker / CacheService 并发测试模式)
"""

import concurrent.futures
import time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.app.database import Base


@pytest.fixture
def db_engine(tmp_path):
    """文件模式 SQLite，允许多线程访问（同生产配置）。"""
    db_path = tmp_path / "test_push_concurrency.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    import backend.app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)

    # 启用外键约束（同生产配置）
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys=ON")

    yield engine
    engine.dispose()


class MockFailingClient:
    """总是失败的 mock 飞书客户端。"""

    def __init__(self):
        self.call_count = 0

    def send_card(self, content):
        self.call_count += 1
        return {
            "success": False,
            "error_type": "network_error",
            "error_message": "timeout",
        }


class TestPushServiceConcurrency:
    """PushService 并发安全测试。"""

    def test_concurrent_record_failure_no_lost_updates(self, db_engine):
        """多个线程并发发送失败，consecutive_failures 应等于实际失败次数。

        先初始化 feishu 通道记录，避免 _get_or_create 的主键冲突干扰本测试焦点。
        """
        from backend.app.models.push_channel import PushChannel
        from backend.app.schemas.push import PushMessageRequest
        from backend.app.services.push_service import PushService

        num_threads = 5

        # 预初始化通道记录
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
        init_session = SessionLocal()
        init_session.add(
            PushChannel(name="feishu", status="active", consecutive_failures=0)
        )
        init_session.commit()
        init_session.close()

        def send_one(_):
            session = SessionLocal()
            try:
                feishu = MockFailingClient()
                service = PushService(db=session, feishu_client=feishu)
                message = PushMessageRequest(
                    message_type="alert",
                    priority="normal",
                    content={"stock_code": "600519"},
                )
                # 在线程中调用 send()：无 running loop → RuntimeError → 走同步路径
                service.send(message)
                # 给 to_thread 异步任务一点时间完成（若环境有 loop）
                time.sleep(0.3)
                session.close()
                return True
            except Exception as e:
                print(f"Exception in thread: {e}")
                session.close()
                return False

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(send_one, i) for i in range(num_threads)]
            successes = sum(f.result() for f in concurrent.futures.as_completed(futures))

        # 验证最终失败计数
        final_session = SessionLocal()
        try:
            record = final_session.get(PushChannel, "feishu")
            assert record is not None
            # _try_channel 内部重试 3 次，但 _record_channel_failure 在 _try_channel
            # 返回后才调用一次（按最终失败结果记录）。因此每个 send() 只加 1。
            expected = successes
            assert record.consecutive_failures == expected, (
                f"Expected {expected} failures, got {record.consecutive_failures}. "
                f"Lost updates detected! (successes={successes})"
            )
        finally:
            final_session.close()

    def test_concurrent_send_creates_distinct_logs(self, db_engine):
        """并发发送不同消息，每个消息应产生独立的 PushLog 记录。"""
        from backend.app.schemas.push import PushMessageRequest
        from backend.app.services.push_service import PushService

        num_threads = 5

        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)

        def send_one(i):
            session = SessionLocal()
            try:
                feishu = MockFailingClient()
                service = PushService(db=session, feishu_client=feishu)
                message = PushMessageRequest(
                    message_type="alert",
                    priority="normal",
                    content={"stock_code": f"60051{i}"},
                )
                msg_id = service.send(message)
                time.sleep(0.3)
                session.close()
                return msg_id
            except Exception as e:
                print(f"Exception: {e}")
                session.close()
                return None

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(send_one, i) for i in range(num_threads)]
            msg_ids = [f.result() for f in concurrent.futures.as_completed(futures)]

        # 验证所有 msg_id 都不为 None 且互不相同
        valid_ids = [mid for mid in msg_ids if mid is not None]
        assert (
            len(valid_ids) == num_threads
        ), f"Only {len(valid_ids)}/{num_threads} messages succeeded"
        assert len(set(valid_ids)) == num_threads, "Duplicate message IDs detected"

        # 验证数据库中有 num_threads 条记录
        final_session = SessionLocal()
        try:
            from backend.app.models.push_log import PushLog

            count = final_session.query(PushLog).count()
            assert count == num_threads, f"Expected {num_threads} logs, got {count}"
        finally:
            final_session.close()

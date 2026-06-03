"""并发竞态测试 — CircuitBreaker 与 CacheService 的并发读写安全性。

覆盖 test-routing-advisor 标出的结构性缺口：
- CircuitBreaker 并发 record_failure 的丢失更新
- CircuitBreaker 并发 _get_or_create 的主键冲突
- CacheService 并发 set 的主键冲突与最终一致性

栈: Python + SQLAlchemy 2.0 + SQLite (check_same_thread=False)
工具: concurrent.futures.ThreadPoolExecutor (标准库)
"""

import concurrent.futures

import pytest

from backend.app.core.circuit_breaker import CircuitBreaker, CircuitState
from backend.app.database import Base, SessionLocal, engine
from backend.app.models.cache_entry import CacheEntry
from backend.app.models.data_source_status import DataSourceStatus
from backend.app.services.cache_service import CacheService


@pytest.fixture(autouse=True, scope="module")
def _setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.rollback()
    session.query(CacheEntry).delete()
    session.query(DataSourceStatus).delete()
    session.commit()
    session.close()


class TestCircuitBreakerConcurrency:
    """CircuitBreaker 并发测试。"""

    def test_concurrent_record_failure_no_lost_updates(self, db):
        """多个线程并发调用 record_failure，consecutive_failures 应等于成功次数。

        先初始化记录，避免 _get_or_create 的主键冲突干扰本测试焦点。
        """
        num_threads = 5

        # 预初始化记录
        init_session = SessionLocal()
        init_cb = CircuitBreaker(init_session)
        init_cb._get_or_create("akshare")
        init_session.close()

        def record_one(_):
            session = SessionLocal()
            cb = CircuitBreaker(session)
            try:
                cb.record_failure("akshare", error="timeout")
                session.close()
                return True
            except Exception:
                session.close()
                return False

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(record_one, i) for i in range(num_threads)]
            successes = sum(f.result() for f in futures)

        # 验证最终失败计数等于成功调用的次数
        final_session = SessionLocal()
        try:
            cb = CircuitBreaker(final_session)
            record = cb._get_or_create("akshare")
            assert record.consecutive_failures == successes, (
                f"Expected {successes} failures, got {record.consecutive_failures}. "
                "Lost updates detected!"
            )
        finally:
            final_session.close()

    def test_concurrent_get_or_create_no_duplicate_key(self, db):
        """多个线程并发 _get_or_create 同一 key，不应产生主键冲突。"""
        num_threads = 5

        def create_one(_):
            session = SessionLocal()
            cb = CircuitBreaker(session)
            try:
                cb._get_or_create("baostock")
                session.close()
                return True
            except Exception:
                session.close()
                return False

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(create_one, i) for i in range(num_threads)]
            successes = sum(f.result() for f in futures)

        # 所有线程都应成功（无 IntegrityError）
        assert successes == num_threads, (
            f"Only {successes}/{num_threads} threads succeeded. "
            "Duplicate key errors detected in concurrent _get_or_create!"
        )

        # 验证只有一条记录
        final_session = SessionLocal()
        try:
            record = final_session.get(DataSourceStatus, "baostock")
            assert record is not None
        finally:
            final_session.close()


class TestCacheServiceConcurrency:
    """CacheService 并发测试。"""

    def test_concurrent_set_no_lost_updates(self, db):
        """多个线程并发 set 同一 key，最终值应来自某次成功写入。"""
        num_threads = 5

        def set_one(i):
            session = SessionLocal()
            cache = CacheService(session)
            try:
                cache.set("concurrent_key", f'{{"value": {i}}}')
                session.close()
                return True
            except Exception:
                session.close()
                return False

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(set_one, i) for i in range(num_threads)]
            successes = sum(f.result() for f in futures)

        # 至少有一次成功写入
        assert successes > 0

        # 验证最终值是某次有效写入
        final_session = SessionLocal()
        try:
            cache = CacheService(final_session)
            result = cache.get("concurrent_key")
            assert result is not None, "No value found after concurrent sets"
            assert '"value":' in result, f"Unexpected value: {result}"
        finally:
            final_session.close()

    def test_concurrent_set_and_get_consistency(self, db):
        """并发 set + get 混合，get 不应读到中间态或损坏数据。"""
        num_writers = 3
        num_readers = 3

        def writer(i):
            session = SessionLocal()
            cache = CacheService(session)
            try:
                cache.set("mixed_key", f'{{"writer": {i}}}')
            finally:
                session.close()

        def reader(_):
            session = SessionLocal()
            cache = CacheService(session)
            try:
                val = cache.get("mixed_key")
                if val is not None:
                    assert '"writer":' in val or val == "", f"Corrupted value: {val}"
            finally:
                session.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            writer_futures = [executor.submit(writer, i) for i in range(num_writers)]
            reader_futures = [executor.submit(reader, i) for i in range(num_readers)]
            for future in concurrent.futures.as_completed(writer_futures + reader_futures):
                future.result()  # 异常会在这里重新抛出

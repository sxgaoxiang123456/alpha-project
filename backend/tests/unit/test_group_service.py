import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.database import Base
from backend.app.models.group import DEFAULT_GROUP_ID, DEFAULT_GROUP_NAME, Group
from backend.app.models.stock import Stock
from backend.app.models.watchlist import WatchlistItem


def _make_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    return Session()


def _add_default_group(db):
    db.add(Group(id=DEFAULT_GROUP_ID, name=DEFAULT_GROUP_NAME, is_default=True))
    db.commit()


def _add_stock(db, code: str, name: str):
    s = Stock(code=code, name=name, market="沪", status="正常")
    db.add(s)
    db.commit()
    return s


def _add_group(db, name: str):
    g = Group(name=name)
    db.add(g)
    db.commit()
    db.refresh(g)
    return g


def _add_watchlist(db, code: str, group_id: int):
    w = WatchlistItem(stock_code=code, group_id=group_id)
    db.add(w)
    db.commit()
    return w


class TestDeleteGroup:
    def test_delete_group_move_to_default_moves_stocks(self):
        from backend.app.services.group_service import delete_group

        db = _make_db()
        _add_default_group(db)
        _add_stock(db, "600000", "股票1")
        _add_stock(db, "600001", "股票2")
        _add_stock(db, "600002", "股票3")

        group = _add_group(db, "持仓")
        _add_watchlist(db, "600000", group.id)
        _add_watchlist(db, "600001", group.id)
        _add_watchlist(db, "600002", group.id)

        group_id = group.id
        result = delete_group(db, group_id, strategy="move_to_default")

        assert result["moved_count"] == 3
        assert result["deleted_count"] == 0

        # 验证股票已移到默认分组
        items = db.query(WatchlistItem).filter_by(group_id=DEFAULT_GROUP_ID).all()
        assert len(items) == 3
        codes = {item.stock_code for item in items}
        assert codes == {"600000", "600001", "600002"}

        # 验证原分组已删除
        assert db.get(Group, group_id) is None

    def test_delete_group_delete_all_removes_stocks(self):
        from backend.app.services.group_service import delete_group

        db = _make_db()
        _add_default_group(db)
        _add_stock(db, "600000", "股票1")
        _add_stock(db, "600001", "股票2")

        group = _add_group(db, "观察")
        _add_watchlist(db, "600000", group.id)
        _add_watchlist(db, "600001", group.id)

        group_id = group.id
        result = delete_group(db, group_id, strategy="delete_all")

        assert result["moved_count"] == 0
        assert result["deleted_count"] == 2

        # 验证股票已全部删除
        items = db.query(WatchlistItem).all()
        assert len(items) == 0

        # 验证原分组已删除
        assert db.get(Group, group_id) is None

    def test_delete_default_group_raises_error(self):
        from backend.app.services.group_service import CannotDeleteDefaultGroupError, delete_group

        db = _make_db()
        _add_default_group(db)

        with pytest.raises(CannotDeleteDefaultGroupError):
            delete_group(db, DEFAULT_GROUP_ID, strategy="move_to_default")

    def test_delete_nonexistent_group_returns_none(self):
        from backend.app.services.group_service import delete_group

        db = _make_db()
        _add_default_group(db)

        result = delete_group(db, 999, strategy="move_to_default")
        assert result is None

    def test_delete_empty_group_succeeds(self):
        from backend.app.services.group_service import delete_group

        db = _make_db()
        _add_default_group(db)

        group = _add_group(db, "空分组")
        group_id = group.id
        result = delete_group(db, group_id, strategy="move_to_default")

        assert result["moved_count"] == 0
        assert result["deleted_count"] == 0
        assert db.get(Group, group_id) is None


class TestFindOrCreateGroup:
    def test_find_existing_group_returns_it(self):
        from backend.app.services.group_service import find_or_create_group

        db = _make_db()
        _add_default_group(db)
        group = _add_group(db, "持仓")

        result = find_or_create_group(db, "持仓")
        assert result["id"] == group.id
        assert result["name"] == "持仓"

    def test_create_new_group_when_not_exists(self):
        from backend.app.services.group_service import find_or_create_group

        db = _make_db()
        _add_default_group(db)

        result = find_or_create_group(db, "新建分组")
        assert result["name"] == "新建分组"
        assert result["id"] != DEFAULT_GROUP_ID

        # 验证数据库中确实创建了
        group = db.query(Group).filter_by(name="新建分组").first()
        assert group is not None

    def test_find_default_group_by_name(self):
        from backend.app.services.group_service import find_or_create_group

        db = _make_db()
        _add_default_group(db)

        result = find_or_create_group(db, DEFAULT_GROUP_NAME)
        assert result["id"] == DEFAULT_GROUP_ID
        assert result["name"] == DEFAULT_GROUP_NAME

import importlib
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateTable


def load_stock_model():
    try:
        from backend.models.stock import Stock
    except ModuleNotFoundError as exc:
        pytest.fail(f"Stock model is not implemented: {exc}", pytrace=False)
    return Stock


def load_group_model():
    try:
        from backend.models.group import Group
    except ModuleNotFoundError as exc:
        pytest.fail(f"Group model is not implemented: {exc}", pytrace=False)
    return Group


def load_watchlist_model():
    try:
        from backend.models.watchlist import WatchlistItem
    except ModuleNotFoundError as exc:
        pytest.fail(f"WatchlistItem model is not implemented: {exc}", pytrace=False)
    return WatchlistItem


def import_fresh_database():
    for module_name in (
        "backend.main",
        "backend.models.watchlist",
        "backend.models.stock",
        "backend.models.group",
        "backend.models",
        "backend.database",
        "backend.config",
    ):
        sys.modules.pop(module_name, None)
    return importlib.import_module("backend.database")


def import_fresh_app_main():
    import_fresh_database()
    return importlib.import_module("backend.main")


def test_app_lifespan_initializes_stock_table_via_init_db(monkeypatch, tmp_path):
    database_path = tmp_path / "watchlist.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    main = import_fresh_app_main()

    try:
        with TestClient(main.app) as client:
            assert client.get("/health").status_code == 200

        inspection_engine = create_engine(f"sqlite:///{database_path}")
        try:
            table_names = inspect(inspection_engine).get_table_names()
        finally:
            inspection_engine.dispose()

        assert "stocks" in table_names
    finally:
        database = sys.modules.get("backend.database")
        if database is not None:
            database.engine.dispose()


def test_app_lifespan_initializes_watchlist_table_via_init_db(monkeypatch, tmp_path):
    database_path = tmp_path / "watchlist.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    main = import_fresh_app_main()

    try:
        with TestClient(main.app) as client:
            assert client.get("/health").status_code == 200

        inspection_engine = create_engine(f"sqlite:///{database_path}")
        try:
            table_names = inspect(inspection_engine).get_table_names()
        finally:
            inspection_engine.dispose()

        assert "watchlist_items" in table_names
    finally:
        database = sys.modules.get("backend.database")
        if database is not None:
            database.engine.dispose()


def test_app_lifespan_initializes_default_group_idempotently(monkeypatch, tmp_path):
    database_path = tmp_path / "watchlist.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    main = import_fresh_app_main()

    try:
        with TestClient(main.app) as client:
            assert client.get("/health").status_code == 200

        database = sys.modules["backend.database"]
        database.init_db()

        inspection_engine = create_engine(f"sqlite:///{database_path}")
        try:
            table_names = inspect(inspection_engine).get_table_names()
            with inspection_engine.connect() as connection:
                group_rows = connection.execute(
                    text("SELECT id, name, is_default FROM groups ORDER BY id")
                ).mappings().all()
        finally:
            inspection_engine.dispose()

        assert "groups" in table_names
        assert len(group_rows) == 1
        default_group = group_rows[0]
        assert default_group["id"] == 1
        assert default_group["name"] == "默认分组"
        assert bool(default_group["is_default"]) is True
    finally:
        database = sys.modules.get("backend.database")
        if database is not None:
            database.engine.dispose()


def test_stock_uses_stocks_table_name():
    Stock = load_stock_model()

    assert Stock.__tablename__ == "stocks"


def test_stock_table_has_required_columns():
    Stock = load_stock_model()

    assert {"code", "name", "market", "sector", "status"}.issubset(
        set(Stock.__table__.columns.keys())
    )


def test_stock_required_columns_have_expected_constraints():
    Stock = load_stock_model()
    columns = Stock.__table__.columns

    assert columns["code"].primary_key or columns["code"].unique
    assert columns["code"].nullable is False
    assert columns["name"].nullable is False
    assert columns["market"].nullable is False


def test_stock_table_can_be_created_and_round_trips_a_stock():
    Stock = load_stock_model()
    engine = create_engine("sqlite:///:memory:")

    try:
        Stock.__table__.create(bind=engine)
        Session = sessionmaker(bind=engine)

        with Session() as session:
            session.add(
                Stock(
                    code="600519",
                    name="贵州茅台",
                    market="沪",
                    sector="白酒",
                    status="正常",
                )
            )
            session.commit()

        with Session() as session:
            stock = session.query(Stock).filter_by(code="600519").one()

        assert stock.name == "贵州茅台"
        assert stock.market == "沪"
        assert stock.sector == "白酒"
        assert stock.status == "正常"
    finally:
        engine.dispose()


def test_group_uses_groups_table_name():
    Group = load_group_model()

    assert Group.__tablename__ == "groups"


def test_group_table_has_required_columns():
    Group = load_group_model()

    assert {"id", "name", "created_at", "is_default"}.issubset(
        set(Group.__table__.columns.keys())
    )


def test_group_required_columns_have_expected_constraints():
    Group = load_group_model()
    columns = Group.__table__.columns

    assert columns["id"].primary_key
    assert columns["id"].nullable is False
    assert columns["name"].nullable is False
    assert columns["name"].unique is True
    assert columns["created_at"].nullable is False
    assert columns["is_default"].nullable is False


def test_group_postgresql_primary_key_identity_starts_at_two():
    Group = load_group_model()

    ddl = str(CreateTable(Group.__table__).compile(dialect=postgresql.dialect()))

    assert "GENERATED BY DEFAULT AS IDENTITY" in ddl
    assert "START WITH 2" in ddl


def test_group_table_can_be_created_and_round_trips_a_group():
    Group = load_group_model()
    engine = create_engine("sqlite:///:memory:")

    try:
        Group.__table__.create(bind=engine)
        Session = sessionmaker(bind=engine)

        with Session() as session:
            session.add(Group(name="观察", is_default=False))
            session.commit()

        with Session() as session:
            group = session.query(Group).filter_by(name="观察").one()

        assert group.id is not None
        assert group.name == "观察"
        assert group.created_at is not None
        assert group.is_default is False
    finally:
        engine.dispose()


def test_watchlist_uses_watchlist_items_table_name():
    WatchlistItem = load_watchlist_model()

    assert WatchlistItem.__tablename__ == "watchlist_items"


def test_watchlist_table_has_required_columns():
    WatchlistItem = load_watchlist_model()

    assert {"id", "stock_code", "group_id", "added_at", "cost_price", "shares"}.issubset(
        set(WatchlistItem.__table__.columns.keys())
    )


def test_watchlist_required_columns_have_expected_constraints():
    WatchlistItem = load_watchlist_model()
    columns = WatchlistItem.__table__.columns

    assert columns["id"].primary_key
    assert columns["id"].nullable is False
    assert columns["stock_code"].nullable is False
    assert columns["stock_code"].unique is True
    assert columns["group_id"].nullable is False
    assert columns["added_at"].nullable is False
    assert columns["cost_price"].nullable is True
    assert columns["shares"].nullable is True


def test_watchlist_foreign_keys_reference_stock_code_and_group_id():
    WatchlistItem = load_watchlist_model()

    foreign_keys = {
        foreign_key.parent.name: (
            foreign_key.column.table.name,
            foreign_key.column.name,
        )
        for foreign_key in WatchlistItem.__table__.foreign_keys
    }

    assert foreign_keys["stock_code"] == ("stocks", "code")
    assert foreign_keys["group_id"] == ("groups", "id")


def test_watchlist_stock_code_is_unique_and_duplicate_insert_raises_integrity_error():
    from backend.database import Base

    Group = load_group_model()
    Stock = load_stock_model()
    WatchlistItem = load_watchlist_model()
    engine = create_engine("sqlite:///:memory:")

    try:
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)

        with Session() as session:
            session.add_all(
                [
                    Stock(code="600519", name="贵州茅台", market="沪", sector="白酒"),
                    Group(id=1, name="默认分组", is_default=True),
                    WatchlistItem(stock_code="600519", group_id=1),
                    WatchlistItem(stock_code="600519", group_id=1),
                ]
            )

            with pytest.raises(IntegrityError):
                session.commit()
    finally:
        engine.dispose()


def test_watchlist_sqlite_init_db_rejects_missing_stock_and_group_foreign_keys(
    monkeypatch, tmp_path
):
    database_path = tmp_path / "watchlist.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    database = import_fresh_database()

    try:
        database.init_db()
        from backend.models.watchlist import WatchlistItem

        with database.SessionLocal() as session:
            session.add(WatchlistItem(stock_code="999999", group_id=999))

            with pytest.raises(IntegrityError):
                session.commit()
    finally:
        database.engine.dispose()


def test_watchlist_round_trips_stock_group_and_optional_holding_fields():
    from decimal import Decimal

    from backend.database import Base

    Group = load_group_model()
    Stock = load_stock_model()
    WatchlistItem = load_watchlist_model()
    engine = create_engine("sqlite:///:memory:")

    try:
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)

        with Session() as session:
            session.add_all(
                [
                    Stock(code="600519", name="贵州茅台", market="沪", sector="白酒"),
                    Stock(code="000001", name="平安银行", market="深", sector=None),
                    Group(id=1, name="默认分组", is_default=True),
                    WatchlistItem(
                        stock_code="600519",
                        group_id=1,
                        cost_price=Decimal("1500.50"),
                        shares=100,
                    ),
                    WatchlistItem(stock_code="000001", group_id=1),
                ]
            )
            session.commit()

        with Session() as session:
            item_with_holding = session.query(WatchlistItem).filter_by(stock_code="600519").one()
            item_without_holding = session.query(WatchlistItem).filter_by(stock_code="000001").one()

            assert item_with_holding.stock.name == "贵州茅台"
            assert item_with_holding.group.name == "默认分组"
            assert item_with_holding.cost_price == Decimal("1500.50")
            assert item_with_holding.shares == 100
            assert item_without_holding.cost_price is None
            assert item_without_holding.shares is None
            assert item_without_holding.added_at is not None
    finally:
        engine.dispose()

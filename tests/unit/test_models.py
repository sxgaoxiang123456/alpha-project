import importlib
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateTable


def load_stock_model():
    try:
        from app.models.stock import Stock
    except ModuleNotFoundError as exc:
        pytest.fail(f"Stock model is not implemented: {exc}", pytrace=False)
    return Stock


def load_group_model():
    try:
        from app.models.group import Group
    except ModuleNotFoundError as exc:
        pytest.fail(f"Group model is not implemented: {exc}", pytrace=False)
    return Group


def import_fresh_app_main():
    for module_name in (
        "app.main",
        "app.models.stock",
        "app.models.group",
        "app.models",
        "app.database",
        "app.config",
    ):
        sys.modules.pop(module_name, None)
    return importlib.import_module("app.main")


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
        database = sys.modules.get("app.database")
        if database is not None:
            database.engine.dispose()


def test_app_lifespan_initializes_default_group_idempotently(monkeypatch, tmp_path):
    database_path = tmp_path / "watchlist.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    main = import_fresh_app_main()

    try:
        with TestClient(main.app) as client:
            assert client.get("/health").status_code == 200

        database = sys.modules["app.database"]
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
        database = sys.modules.get("app.database")
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

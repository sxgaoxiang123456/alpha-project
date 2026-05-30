import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def load_stock_model():
    try:
        from app.models.stock import Stock
    except ModuleNotFoundError as exc:
        pytest.fail(f"Stock model is not implemented: {exc}", pytrace=False)
    return Stock


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

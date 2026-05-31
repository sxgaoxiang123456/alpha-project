from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类。"""


settings = get_settings()


def _ensure_sqlite_parent_dir(database_url: str) -> None:
    url = make_url(database_url)
    if url.drivername != "sqlite" or not url.database or url.database == ":memory:":
        return

    database_path = Path(url.database)
    if database_path.parent != Path("."):
        database_path.parent.mkdir(parents=True, exist_ok=True)


def _create_engine(database_url: str):
    connect_args = {}
    if database_url.startswith("sqlite"):
        _ensure_sqlite_parent_dir(database_url)
        connect_args = {"check_same_thread": False}

    return create_engine(database_url, connect_args=connect_args)


engine = _create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """按当前已注册的 SQLAlchemy metadata 建表。"""

    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)

from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from backend.app.config import get_settings


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
    is_sqlite = database_url.startswith("sqlite")
    if is_sqlite:
        _ensure_sqlite_parent_dir(database_url)
        connect_args = {"check_same_thread": False}

    created_engine = create_engine(database_url, connect_args=connect_args)

    if is_sqlite:
        @event.listens_for(created_engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return created_engine


engine = _create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """按当前已注册的 SQLAlchemy metadata 建表，并初始化系统默认数据。"""

    import backend.app.models  # noqa: F401
    from backend.app.models.group import DEFAULT_GROUP_ID, DEFAULT_GROUP_NAME, Group

    Base.metadata.create_all(bind=engine)

    with SessionLocal() as session:
        if session.get(Group, DEFAULT_GROUP_ID) is None:
            session.add(
                Group(
                    id=DEFAULT_GROUP_ID,
                    name=DEFAULT_GROUP_NAME,
                    is_default=True,
                )
            )
            session.commit()

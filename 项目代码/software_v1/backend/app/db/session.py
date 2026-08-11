import os
from threading import Lock

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker


_engine = None
_session_factory = None
_database_lock = Lock()


def create_engine_from_url(database_url: str):
    return create_engine(database_url, pool_pre_ping=True)


def get_session_factory(database_url: str):
    engine = create_engine_from_url(database_url)
    return engine, sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    factory = initialize_database()
    with factory() as session:
        yield session


def initialize_database(database_url: str | None = None):
    global _engine, _session_factory
    if _session_factory is not None:
        return _session_factory
    with _database_lock:
        if _session_factory is None:
            _engine, _session_factory = get_session_factory(
                database_url or database_url_from_env()
            )
    return _session_factory


def dispose_database() -> None:
    global _engine, _session_factory
    with _database_lock:
        if _engine is not None:
            _engine.dispose()
        _engine = None
        _session_factory = None


def database_url_from_env() -> str:
    """Read the database URL from the environment; never accept it from a request."""
    value = os.getenv("DATABASE_URL")
    if not value:
        raise RuntimeError("DATABASE_URL is required")
    return value


def create_async_engine_from_url(database_url: str) -> AsyncEngine:
    url = database_url
    if url.startswith("mysql+pymysql://"):
        url = url.replace("mysql+pymysql://", "mysql+aiomysql://", 1)
    return create_async_engine(url, pool_pre_ping=True)


def get_async_session_factory(database_url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine_from_url(database_url)
    return engine, async_sessionmaker(engine, expire_on_commit=False)

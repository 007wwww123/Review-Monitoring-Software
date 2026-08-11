import os

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker


def create_engine_from_url(database_url: str):
    return create_engine(database_url, pool_pre_ping=True)


def get_session_factory(database_url: str):
    engine = create_engine_from_url(database_url)
    return engine, sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    engine, factory = get_session_factory(database_url_from_env())
    try:
        with factory() as session:
            yield session
    finally:
        engine.dispose()


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

"""PostgreSQL engine and session management."""

from collections.abc import Generator
from contextlib import contextmanager
from threading import Lock
from typing import Any

from sqlalchemy import Engine, create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.db.models import Base

engine: Engine | None = None
_engine_lock = Lock()


class _LazySessionMaker(sessionmaker[Session]):
    """Session factory that resolves database configuration when called."""

    def __call__(self, **local_kw: Any) -> Session:
        get_engine()
        return super().__call__(**local_kw)


SessionLocal = _LazySessionMaker(
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


def get_engine() -> Engine:
    """Create and cache the engine on first database use."""
    global engine

    if engine is not None:
        return engine

    with _engine_lock:
        if engine is None:
            postgres_url = get_settings().postgres_url
            if postgres_url is None or not postgres_url.get_secret_value().strip():
                raise RuntimeError(
                    "POSTGRES_URL is not set. Add it to backend/.env."
                )
            created_engine = create_engine(
                postgres_url.get_secret_value(),
                pool_pre_ping=True,
            )
            SessionLocal.configure(bind=created_engine)
            engine = created_engine

    return engine


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Yield a session and close it, reporting database connectivity failures."""
    get_engine()
    with SessionLocal() as session:
        try:
            yield session
        except SQLAlchemyError as error:
            raise RuntimeError("Database error.") from error


def init_db() -> None:
    """Create all tables defined in the shared metadata."""
    try:
        Base.metadata.create_all(bind=get_engine())
    except SQLAlchemyError as error:
        raise RuntimeError("Unable to initialize the PostgreSQL database.") from error

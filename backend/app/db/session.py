"""FastAPI dependency for database sessions."""

from typing import Generator

from sqlalchemy.orm import Session

from app.db.engine import get_session_factory


def get_db_session() -> Generator[Session, None, None]:
    """Yield a database session for use in FastAPI endpoints.

    FastAPI automatically runs sync dependencies in a thread pool,
    so this works seamlessly with the async request lifecycle.

    Usage in a router:
        @router.get("/example")
        def example(db: Session = Depends(get_db_session)):
            ...
    """
    factory = get_session_factory()
    session = factory()
    try:
        yield session
    finally:
        session.close()

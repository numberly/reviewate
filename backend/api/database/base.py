"""SQLAlchemy database base configuration."""

from collections.abc import Generator

from sqlalchemy.orm import Session

from api.context import get_current_app
from api.models.base import Base


def get_session() -> Generator[Session]:
    """Get a database session (FastAPI dependency).

    Yields:
        Database session

    Example:
        ```python
        @router.get("/users")
        def get_users(db: Session = Depends(get_session)):
            return db.query(User).all()
        ```
    """
    app = get_current_app()
    if not app.database:
        raise RuntimeError("Database plugin not enabled")

    db = app.database.get_session()
    try:
        yield db
    finally:
        db.close()


__all__ = ["Base", "get_session"]

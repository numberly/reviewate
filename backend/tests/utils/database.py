"""Database fixtures for testing."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.database.base import Base

# Test database configuration
TEST_DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/reviewate_dev"


@pytest.fixture(scope="session")
def db_engine():
    """Create a PostgreSQL database engine for testing."""
    engine = create_engine(TEST_DATABASE_URL, echo=False, pool_pre_ping=True)

    # Drop all tables first to ensure clean schema (handles model changes)
    Base.metadata.drop_all(bind=engine)

    # Create all tables with current schema
    Base.metadata.create_all(bind=engine)

    yield engine

    # Drop all tables after tests
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(db_engine):
    """Create a database session with transaction rollback for isolation."""
    connection = db_engine.connect()
    transaction = connection.begin()

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=connection)
    session = SessionLocal()

    yield session

    session.close()
    transaction.rollback()
    connection.close()

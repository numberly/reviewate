"""Tests for auth dependencies."""

from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from api.models import User
from api.routers.auth.dependencies import get_current_user, get_current_user_optional
from api.routers.auth.jwt import create_access_token


@pytest.mark.asyncio
async def test_get_current_user_valid_token(create_user: User, db_session: Session, test_app):
    """Test get_current_user with valid token."""
    # Create valid token
    token = create_access_token(create_user.id)

    # Get user (manages its own session via app.database.session())
    user = await get_current_user(token)

    assert user is not None
    assert user.id == create_user.id
    assert user.email == create_user.email


@pytest.mark.asyncio
async def test_get_current_user_no_token(db_session: Session, test_app):
    """Test get_current_user with no token raises 401."""
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(None)

    assert exc_info.value.status_code == 401
    assert "Not authenticated" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_current_user_invalid_token(db_session: Session, test_app):
    """Test get_current_user with invalid token raises 401."""
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user("invalid.token.here")

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_user_not_found(db_session: Session, test_app):
    """Test get_current_user with valid token but user doesn't exist."""
    # Create token for non-existent user
    fake_user_id = uuid4()
    token = create_access_token(fake_user_id)

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token)

    assert exc_info.value.status_code == 401
    assert "User not found" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_current_user_optional_valid_token(
    create_user: User, db_session: Session, test_app
):
    """Test get_current_user_optional with valid token."""
    # Create valid token
    token = create_access_token(create_user.id)

    # Get user (manages its own session via app.database.session())
    user = await get_current_user_optional(token)

    assert user is not None
    assert user.id == create_user.id
    assert user.email == create_user.email


@pytest.mark.asyncio
async def test_get_current_user_optional_no_token(db_session: Session, test_app):
    """Test get_current_user_optional with no token returns None."""
    user = await get_current_user_optional(None)

    assert user is None


@pytest.mark.asyncio
async def test_get_current_user_optional_invalid_token(db_session: Session, test_app):
    """Test get_current_user_optional with invalid token returns None."""
    user = await get_current_user_optional("invalid.token")

    assert user is None


@pytest.mark.asyncio
async def test_get_current_user_optional_user_not_found(db_session: Session, test_app):
    """Test get_current_user_optional with valid token but user doesn't exist returns None."""
    # Create token for non-existent user
    fake_user_id = uuid4()
    token = create_access_token(fake_user_id)

    user = await get_current_user_optional(token)

    assert user is None

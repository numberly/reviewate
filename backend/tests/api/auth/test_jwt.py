"""Tests for JWT token creation and verification."""

from datetime import UTC, datetime
from uuid import uuid4

import jwt
import pytest
from fastapi import HTTPException

from api.routers.auth.jwt import create_access_token, verify_access_token


def test_create_access_token(test_app):
    """Test creating a JWT access token."""
    user_id = uuid4()
    token = create_access_token(user_id)

    assert token is not None
    assert isinstance(token, str)
    assert len(token) > 0


def test_verify_access_token_valid(test_app):
    """Test verifying a valid JWT token."""
    user_id = uuid4()
    token = create_access_token(user_id)

    verified_user_id = verify_access_token(token)
    assert verified_user_id == user_id


def test_verify_access_token_invalid(test_app):
    """Test verifying an invalid JWT token raises error."""
    with pytest.raises(HTTPException) as exc_info:
        verify_access_token("invalid.token.here")

    assert exc_info.value.status_code == 401
    assert "Invalid token" in exc_info.value.detail


def test_verify_access_token_malformed(test_app):
    """Test verifying a malformed JWT token raises error."""
    with pytest.raises(HTTPException) as exc_info:
        verify_access_token("notavalidtoken")

    assert exc_info.value.status_code == 401


def test_token_contains_correct_claims(test_app):
    """Test that token contains correct claims."""
    user_id = uuid4()
    token = create_access_token(user_id)

    # Decode without verification to check payload
    payload = jwt.decode(token, options={"verify_signature": False})

    assert "sub" in payload
    assert payload["sub"] == str(user_id)
    assert "exp" in payload
    assert "iat" in payload


def test_token_expiration_claim(test_app):
    """Test that token has expiration claim."""
    user_id = uuid4()
    token = create_access_token(user_id)

    payload = jwt.decode(token, options={"verify_signature": False})
    exp_timestamp = payload["exp"]
    exp_datetime = datetime.fromtimestamp(exp_timestamp, UTC)

    # Should expire in approximately 30 days (from config)
    now = datetime.now(UTC)
    days_until_expiry = (exp_datetime - now).days

    assert 29 <= days_until_expiry <= 31  # Allow some margin

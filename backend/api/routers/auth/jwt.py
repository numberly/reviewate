"""JWT token creation and verification."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from fastapi import HTTPException

from api.context import get_current_app


def create_access_token(user_id: UUID) -> str:
    """Create a JWT access token for a user.

    Args:
        user_id: The user's UUID
        config: Backend configuration (deprecated, uses app context if not provided)

    Returns:
        JWT token string
    """
    app = get_current_app()
    jwt_config = app.web.config.jwt

    expire = datetime.now(UTC) + timedelta(days=jwt_config.token_expire_days)

    payload = {
        "sub": str(user_id),  # Subject (user ID)
        "exp": expire,  # Expiration time
        "iat": datetime.now(UTC),  # Issued at
    }

    token = jwt.encode(payload, jwt_config.secret_key, algorithm=jwt_config.algorithm)
    return token


def verify_access_token(token: str) -> UUID:
    """Verify a JWT token and return the user ID.

    Args:
        token: JWT token string

    Returns:
        User UUID

    Raises:
        HTTPException: If token is invalid or expired
    """
    app = get_current_app()
    jwt_config = app.web.config.jwt

    try:
        payload = jwt.decode(token, jwt_config.secret_key, algorithms=[jwt_config.algorithm])
        user_id_str = payload.get("sub")

        if not user_id_str:
            raise HTTPException(status_code=401, detail="Invalid token")

        return UUID(user_id_str)

    except jwt.ExpiredSignatureError as e:
        raise HTTPException(status_code=401, detail=f"Token expired: {e}") from e
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}") from e
    except ValueError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token format: {e}") from e

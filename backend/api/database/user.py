"""Database operations for User model."""

from uuid import UUID

from sqlalchemy.orm import Session

from api.database.identity import db_get_or_create_provider_identity
from api.models.identities import ProviderIdentity
from api.models.users import User
from api.routers.auth.enums import OAuthProvider


def db_get_user_by_id(db: Session, user_id: UUID) -> User | None:
    """Get user by ID.

    Args:
        db: Database session
        user_id: User UUID

    Returns:
        User if found, None otherwise
    """
    return db.query(User).filter(User.id == user_id).first()


def db_get_user_by_email(db: Session, email: str) -> User | None:
    """Get user by email.

    Args:
        db: Database session
        email: User email

    Returns:
        User if found, None otherwise
    """
    return db.query(User).filter(User.email == email).first()


def db_create_or_update_user(
    db: Session,
    provider: OAuthProvider,
    external_id: str,
    email: str,
    username: str,
    avatar_url: str | None = None,
) -> tuple[User, bool]:
    """Create or update user with OAuth data.

    This function handles both account creation and provider linking:
    1. Find or create ProviderIdentity for the provider
    2. If identity has user_id, use that user
    3. Else if email provided, find user by email
    4. Else create new user
    5. Link identity to user

    Args:
        db: Database session
        provider: OAuth provider
        external_id: External user ID from provider
        email: User email
        username: Platform-specific username
        avatar_url: User's avatar URL from provider (optional)

    Returns:
        Tuple of (User, is_new_user) where is_new_user is True if user was created
    """
    # Step 1: Find or create the provider identity
    identity, _ = db_get_or_create_provider_identity(
        db=db,
        provider=provider.value,
        external_id=external_id,
        username=username,
        avatar_url=avatar_url,
    )

    # Step 2: Find the user
    user = None
    is_new_user = False

    # Check if identity is already linked to a user
    if identity.user_id:
        user = db.query(User).filter(User.id == identity.user_id).first()

    # If not, try to find by email (for account linking)
    if not user and email:
        user = db_get_user_by_email(db, email)

    # If still no user, create one
    if not user:
        user = User(email=email)
        db.add(user)
        db.flush()  # Get the user ID
        is_new_user = True

    # Step 3: Link identity to user if not already linked
    if identity.user_id != user.id:
        identity.user_id = user.id

    # Step 4: Update email if different (email may have changed)
    if email and user.email != email:
        user.email = email

    db.commit()
    db.refresh(user)
    db.refresh(identity)

    return user, is_new_user


def db_get_user_by_identity(
    db: Session,
    provider: str,
    external_id: str,
) -> User | None:
    """Get user by provider identity.

    Args:
        db: Database session
        provider: Provider type (github, gitlab, google)
        external_id: External user ID from provider

    Returns:
        User if found and linked, None otherwise
    """
    identity = (
        db.query(ProviderIdentity)
        .filter(
            ProviderIdentity.provider == provider,
            ProviderIdentity.external_id == external_id,
        )
        .first()
    )

    if identity and identity.user_id:
        return db.query(User).filter(User.id == identity.user_id).first()

    return None

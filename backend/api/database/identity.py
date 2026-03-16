"""Database operations for ProviderIdentity model."""

from uuid import UUID

from sqlalchemy.orm import Session

from api.models.identities import ProviderIdentity


def db_get_or_create_provider_identity(
    db: Session,
    provider: str,
    external_id: str,
    username: str | None = None,
    avatar_url: str | None = None,
    user_id: UUID | None = None,
) -> tuple[ProviderIdentity, bool]:
    """Get or create a provider identity.

    Args:
        db: Database session
        provider: Provider type (github, gitlab, google)
        external_id: External user ID from provider
        username: Provider username (optional)
        avatar_url: Provider avatar URL (optional)
        user_id: Linked Reviewate user ID (optional)

    Returns:
        Tuple of (ProviderIdentity, is_new) where is_new is True if created
    """
    # Try to find existing identity
    identity = (
        db.query(ProviderIdentity)
        .filter(
            ProviderIdentity.provider == provider,
            ProviderIdentity.external_id == external_id,
        )
        .first()
    )

    if identity:
        # Update fields if provided
        if username is not None:
            identity.username = username
        if avatar_url is not None:
            identity.avatar_url = avatar_url
        if user_id is not None and identity.user_id is None:
            # Only set user_id if not already set
            identity.user_id = user_id
        db.commit()
        db.refresh(identity)
        return identity, False

    # Create new identity
    identity = ProviderIdentity(
        provider=provider,
        external_id=external_id,
        username=username,
        avatar_url=avatar_url,
        user_id=user_id,
    )
    db.add(identity)
    db.commit()
    db.refresh(identity)
    return identity, True


def db_get_identity_by_id(db: Session, identity_id: UUID) -> ProviderIdentity | None:
    """Get a provider identity by ID.

    Args:
        db: Database session
        identity_id: Identity UUID

    Returns:
        ProviderIdentity if found, None otherwise
    """
    return db.query(ProviderIdentity).filter(ProviderIdentity.id == identity_id).first()


def db_get_identity_by_external_id(
    db: Session,
    provider: str,
    external_id: str,
) -> ProviderIdentity | None:
    """Get identity by provider and external ID.

    Args:
        db: Database session
        provider: Provider type (github, gitlab, google)
        external_id: External user ID from provider

    Returns:
        ProviderIdentity if found, None otherwise
    """
    return (
        db.query(ProviderIdentity)
        .filter(
            ProviderIdentity.provider == provider,
            ProviderIdentity.external_id == external_id,
        )
        .first()
    )


def db_get_user_identities(db: Session, user_id: UUID) -> list[ProviderIdentity]:
    """Get all identities for a user.

    Args:
        db: Database session
        user_id: User UUID

    Returns:
        List of ProviderIdentity linked to the user
    """
    return db.query(ProviderIdentity).filter(ProviderIdentity.user_id == user_id).all()


def db_link_identity_to_user(
    db: Session,
    identity_id: UUID,
    user_id: UUID,
) -> ProviderIdentity | None:
    """Link a provider identity to a user.

    Args:
        db: Database session
        identity_id: Identity UUID to link
        user_id: User UUID to link to

    Returns:
        Updated ProviderIdentity or None if not found
    """
    identity = db.query(ProviderIdentity).filter(ProviderIdentity.id == identity_id).first()

    if not identity:
        return None

    identity.user_id = user_id
    db.commit()
    db.refresh(identity)
    return identity


def db_link_identities_to_user_by_external_id(
    db: Session,
    provider: str,
    external_id: str,
    user_id: UUID,
) -> int:
    """Link all identities with matching provider/external_id to a user.

    This is called during OAuth login to link existing identities
    (created during member sync) to the user.

    Args:
        db: Database session
        provider: Provider type (github, gitlab, google)
        external_id: External user ID from provider
        user_id: User UUID to link to

    Returns:
        Number of identities updated
    """
    result = (
        db.query(ProviderIdentity)
        .filter(
            ProviderIdentity.provider == provider,
            ProviderIdentity.external_id == external_id,
            ProviderIdentity.user_id.is_(None),  # Only update unlinked identities
        )
        .update({"user_id": user_id})
    )

    db.commit()
    return result


def db_update_identity(
    db: Session,
    identity_id: UUID,
    username: str | None = None,
    avatar_url: str | None = None,
) -> ProviderIdentity | None:
    """Update a provider identity.

    Args:
        db: Database session
        identity_id: Identity UUID
        username: New username (optional)
        avatar_url: New avatar URL (optional)

    Returns:
        Updated ProviderIdentity or None if not found
    """
    identity = db.query(ProviderIdentity).filter(ProviderIdentity.id == identity_id).first()

    if not identity:
        return None

    if username is not None:
        identity.username = username
    if avatar_url is not None:
        identity.avatar_url = avatar_url

    db.commit()
    db.refresh(identity)
    return identity


def db_unlink_identity_from_user(
    db: Session,
    user_id: UUID,
    provider: str,
) -> bool:
    """Unlink a provider identity from a user.

    Sets user_id to None on the identity, effectively disconnecting it.
    Does NOT delete the identity (preserves org member data).

    Args:
        db: Database session
        user_id: User UUID
        provider: Provider type (github, gitlab, google)

    Returns:
        True if identity was found and unlinked, False otherwise
    """
    identity = (
        db.query(ProviderIdentity)
        .filter(
            ProviderIdentity.user_id == user_id,
            ProviderIdentity.provider == provider,
        )
        .first()
    )

    if not identity:
        return False

    identity.user_id = None
    db.commit()
    return True


def db_count_user_identities(db: Session, user_id: UUID) -> int:
    """Count the number of linked identities for a user.

    Args:
        db: Database session
        user_id: User UUID

    Returns:
        Number of linked provider identities
    """
    return db.query(ProviderIdentity).filter(ProviderIdentity.user_id == user_id).count()

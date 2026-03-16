"""Database operations for Organization and OrganizationMembership models."""

from uuid import UUID

from sqlalchemy.orm import Session

from api.models.identities import ProviderIdentity
from api.models.organizations import Organization, OrganizationMembership


def db_create_organization(
    db: Session,
    name: str,
    external_org_id: str,
    installation_id: str,
    provider: str,
    provider_url: str,
    gitlab_access_token_encrypted: str | None = None,
    avatar_url: str | None = None,
) -> Organization:
    """Create a new organization.

    Args:
        db: Database session
        name: Organization name
        external_org_id: External org ID from platform (GitHub/GitLab)
        installation_id: Installation ID
        provider: Provider type (github or gitlab)
        provider_url: Provider URL (e.g., https://github.com or custom GitLab instance)
        gitlab_access_token_encrypted: Encrypted GitLab access token (optional)
        avatar_url: Organization avatar URL from GitHub/GitLab (optional)

    Returns:
        Created Organization
    """
    organization = Organization(
        name=name,
        external_org_id=external_org_id,
        installation_id=installation_id,
        provider=provider,
        provider_url=provider_url,
        gitlab_access_token_encrypted=gitlab_access_token_encrypted,
        avatar_url=avatar_url,
    )
    db.add(organization)
    db.commit()
    db.refresh(organization)

    return organization


def db_create_organization_membership(
    db: Session,
    provider_identity_id: UUID,
    organization_id: UUID,
    role: str = "member",
    reviewate_enabled: bool = True,
) -> OrganizationMembership:
    """Create an organization membership.

    Args:
        db: Database session
        provider_identity_id: Provider identity ID
        organization_id: Organization ID
        role: User role in organization (default: "member")
        reviewate_enabled: Whether Reviewate is enabled for this member

    Returns:
        Created OrganizationMembership
    """
    membership = OrganizationMembership(
        provider_identity_id=provider_identity_id,
        organization_id=organization_id,
        role=role,
        reviewate_enabled=reviewate_enabled,
    )
    db.add(membership)
    db.commit()
    db.refresh(membership)

    return membership


def db_get_organization_by_installation_id(
    db: Session,
    installation_id: str,
) -> Organization | None:
    """Get organization by installation ID.

    Args:
        db: Database session
        installation_id: Installation ID

    Returns:
        Organization if found, None otherwise
    """
    return db.query(Organization).filter(Organization.installation_id == installation_id).first()


def db_get_organization_by_external_id(
    db: Session,
    external_org_id: str,
    provider: str | None = None,
) -> Organization | None:
    """Get organization by external org ID.

    Args:
        db: Database session
        external_org_id: External org ID from platform
        provider: Optional provider filter (github or gitlab)

    Returns:
        Organization if found, None otherwise
    """
    query = db.query(Organization).filter(Organization.external_org_id == external_org_id)
    if provider:
        query = query.filter(Organization.provider == provider)
    return query.first()


def db_delete_organization(
    db: Session,
    installation_id: str,
) -> bool:
    """Delete organization by installation ID.

    Args:
        db: Database session
        installation_id: Installation ID

    Returns:
        True if organization was deleted, False if not found
    """
    organization = db_get_organization_by_installation_id(db, installation_id)
    if organization:
        db.delete(organization)  # Cascade deletes memberships
        db.commit()
        return True
    return False


def db_delete_organization_by_id(
    db: Session,
    organization_id: UUID,
) -> bool:
    """Delete organization by ID.

    Args:
        db: Database session
        organization_id: Organization ID

    Returns:
        True if organization was deleted, False if not found
    """
    organization = db.query(Organization).filter(Organization.id == organization_id).first()
    if organization:
        db.delete(organization)  # Cascade deletes memberships and repositories
        db.commit()
        return True
    return False


def db_get_organization_membership(
    db: Session,
    provider_identity_id: UUID,
    organization_id: UUID,
) -> OrganizationMembership | None:
    """Get organization membership for a provider identity.

    Args:
        db: Database session
        provider_identity_id: Provider identity ID
        organization_id: Organization ID

    Returns:
        OrganizationMembership if found, None otherwise
    """
    return (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.provider_identity_id == provider_identity_id,
            OrganizationMembership.organization_id == organization_id,
        )
        .first()
    )


def db_get_organization_membership_by_id(
    db: Session,
    membership_id: UUID,
) -> OrganizationMembership | None:
    """Get organization membership by ID.

    Args:
        db: Database session
        membership_id: Membership ID

    Returns:
        OrganizationMembership if found, None otherwise
    """
    return (
        db.query(OrganizationMembership).filter(OrganizationMembership.id == membership_id).first()
    )


def db_get_organization_memberships_by_identity(
    db: Session,
    identity_ids: list[UUID],
    organization_id: UUID,
) -> OrganizationMembership | None:
    """Get organization membership for any of the given identities.

    This is used to check if a user (with multiple identities) has access to an org.

    Args:
        db: Database session
        identity_ids: List of provider identity IDs
        organization_id: Organization ID

    Returns:
        OrganizationMembership if found, None otherwise
    """
    if not identity_ids:
        return None

    return (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.provider_identity_id.in_(identity_ids),
            OrganizationMembership.organization_id == organization_id,
        )
        .first()
    )


def db_get_organization_members(
    db: Session,
    organization_id: UUID,
) -> list[OrganizationMembership]:
    """Get all members of an organization.

    Args:
        db: Database session
        organization_id: Organization ID

    Returns:
        List of OrganizationMembership with provider_identity joined
    """
    return (
        db.query(OrganizationMembership)
        .filter(OrganizationMembership.organization_id == organization_id)
        .join(ProviderIdentity)
        .all()
    )


def db_sync_organization_membership(
    db: Session,
    provider_identity_id: UUID,
    organization_id: UUID,
    role: str = "member",
) -> OrganizationMembership:
    """Create organization membership if it doesn't exist, or return existing one.

    This is used during member sync to ensure all org members have memberships.

    Args:
        db: Database session
        provider_identity_id: Provider identity ID
        organization_id: Organization ID
        role: User role in organization (default: "member")

    Returns:
        OrganizationMembership (either existing or newly created)
    """
    # Check if membership already exists
    existing = db_get_organization_membership(db, provider_identity_id, organization_id)
    if existing:
        return existing

    # Create new membership
    return db_create_organization_membership(db, provider_identity_id, organization_id, role)


def db_get_organization_by_id(
    db: Session,
    organization_id: UUID,
) -> Organization | None:
    """Get organization by ID.

    Args:
        db: Database session
        organization_id: Organization ID

    Returns:
        Organization if found, None otherwise
    """
    return db.query(Organization).filter(Organization.id == organization_id).first()


def db_get_all_organizations(
    db: Session,
) -> list[Organization]:
    """Get all organizations.

    Args:
        db: Database session

    Returns:
        List of all organizations
    """
    return db.query(Organization).all()


def db_get_user_organization_ids(
    db: Session,
    identity_ids: list[UUID],
) -> list[UUID]:
    """Get all organization IDs that a user is a member of (via their identities).

    Args:
        db: Database session
        identity_ids: List of provider identity IDs for the user

    Returns:
        List of organization IDs
    """
    if not identity_ids:
        return []

    memberships = (
        db.query(OrganizationMembership.organization_id)
        .filter(OrganizationMembership.provider_identity_id.in_(identity_ids))
        .distinct()
        .all()
    )
    return [membership.organization_id for membership in memberships]


def db_get_user_organizations_with_roles(
    db: Session,
    identity_ids: list[UUID],
) -> list[tuple[Organization, str]]:
    """Get all organizations a user belongs to, with their role.

    Args:
        db: Database session
        identity_ids: List of provider identity IDs for the user

    Returns:
        List of (Organization, role) tuples
    """
    if not identity_ids:
        return []

    return (
        db.query(Organization, OrganizationMembership.role)
        .join(OrganizationMembership)
        .filter(OrganizationMembership.provider_identity_id.in_(identity_ids))
        .all()
    )


def db_update_organization_settings(
    db: Session,
    organization_id: UUID,
    **kwargs: str | bool | None,
) -> Organization | None:
    """Update organization settings.

    Only updates fields that are explicitly passed. Supports:
    - automatic_review_trigger: str | None
    - automatic_summary_trigger: str | None

    Args:
        db: Database session
        organization_id: Organization ID
        **kwargs: Fields to update

    Returns:
        Updated Organization or None if not found
    """
    organization = db_get_organization_by_id(db, organization_id)
    if not organization:
        return None

    for key, value in kwargs.items():
        if hasattr(organization, key):
            setattr(organization, key, value)

    db.commit()
    db.refresh(organization)
    return organization


def db_get_membership_by_username(
    db: Session,
    organization_id: UUID,
    username: str,
) -> OrganizationMembership | None:
    """Get organization membership by username.

    Looks up membership through the linked ProviderIdentity's username.

    Args:
        db: Database session
        organization_id: Organization ID
        username: Username to look up

    Returns:
        OrganizationMembership if found, None otherwise
    """
    return (
        db.query(OrganizationMembership)
        .join(ProviderIdentity)
        .filter(
            OrganizationMembership.organization_id == organization_id,
            ProviderIdentity.username == username,
        )
        .first()
    )


def db_update_member_settings(
    db: Session,
    membership_id: UUID,
    **kwargs: bool | None,
) -> OrganizationMembership | None:
    """Update member settings.

    Only updates fields that are explicitly passed. Supports:
    - reviewate_enabled: bool

    Args:
        db: Database session
        membership_id: Membership ID
        **kwargs: Fields to update

    Returns:
        Updated OrganizationMembership or None if not found
    """
    membership = db_get_organization_membership_by_id(db, membership_id)
    if not membership:
        return None

    for key, value in kwargs.items():
        if hasattr(membership, key) and value is not None:
            setattr(membership, key, value)

    db.commit()
    db.refresh(membership)
    return membership

"""SQLAlchemy database models for users."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.models.base import Base

if TYPE_CHECKING:
    from api.models.identities import ProviderIdentity
    from api.models.repositories import RepositoryMembership


class User(Base):
    """User database model.

    Represents a Reviewate app user. Provider-specific identity data
    (external IDs, usernames, avatars) are stored in ProviderIdentity.

    A user can have multiple provider identities linked to their account.
    """

    __tablename__ = "users"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4, index=True, name="id"
    )

    # User info - email is nullable (can be null for users who haven't logged in yet)
    email: Mapped[str | None] = mapped_column(
        String(255), unique=True, index=True, nullable=True, name="email"
    )

    # Onboarding
    onboarding_step: Mapped[int | None] = mapped_column(
        Integer, nullable=True, default=None, name="onboarding_step"
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), name="created_at"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        name="updated_at",
    )

    # Relationships
    identities: Mapped[list[ProviderIdentity]] = relationship(
        "ProviderIdentity", back_populates="user", cascade="all, delete-orphan"
    )
    repository_memberships: Mapped[list[RepositoryMembership]] = relationship(
        "RepositoryMembership", back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def display_username(self) -> str:
        """Return display username from first identity or email prefix."""
        # Try to get username from linked identities
        for identity in self.identities:
            if identity.username:
                return identity.username
        # Fallback to email prefix
        if self.email:
            return self.email.split("@")[0]
        return f"user-{str(self.id)[:8]}"

    @property
    def avatar_url(self) -> str | None:
        """Return avatar URL from first identity that has one."""
        for identity in self.identities:
            if identity.avatar_url:
                return identity.avatar_url
        return None

    def get_identity(self, provider: str) -> ProviderIdentity | None:
        """Get the identity for a specific provider."""
        for identity in self.identities:
            if identity.provider == provider:
                return identity
        return None

    def __repr__(self) -> str:
        """String representation."""
        return f"<User(id={self.id}, email={self.email})>"

"""SQLAlchemy database models for provider identities."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.models.base import Base

if TYPE_CHECKING:
    from api.models.users import User


class ProviderType(StrEnum):
    """Supported OAuth providers."""

    GITHUB = "github"
    GITLAB = "gitlab"
    GOOGLE = "google"


class ProviderIdentity(Base):
    """Provider identity model.

    Represents a user's identity on a specific provider (GitHub, GitLab, Google).
    Multiple identities can link to one User once they log in.

    This model enables:
    - Storing org members who haven't logged in yet (synced from GitHub/GitLab)
    - Linking multiple provider accounts to a single Reviewate user
    - Clean separation between provider identity and app user
    """

    __tablename__ = "provider_identities"
    __mapper_args__ = {"confirm_deleted_rows": False}

    # Primary key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4, index=True, name="id"
    )

    # Provider information
    provider: Mapped[str] = mapped_column(
        String(20), nullable=False, name="provider"
    )  # github, gitlab, google
    external_id: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True, name="external_id"
    )  # Provider's user ID

    # User data from provider
    username: Mapped[str | None] = mapped_column(
        String(255), nullable=True, name="username"
    )  # Provider username (login for GitHub, username for GitLab)
    avatar_url: Mapped[str | None] = mapped_column(
        String(512), nullable=True, name="avatar_url"
    )  # Provider avatar URL

    # Linked Reviewate user (nullable - set when user logs in)
    user_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL", name="fk_provider_identities_user_id_users"),
        nullable=True,
        index=True,
        name="user_id",
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

    # Unique constraint: one identity per provider per external_id
    __table_args__ = (
        UniqueConstraint(
            "provider", "external_id", name="uq_provider_identity_provider_external_id"
        ),
    )

    # Relationships
    user: Mapped[User | None] = relationship("User", back_populates="identities")

    @property
    def display_name(self) -> str:
        """Return display name for this identity."""
        return self.username or f"{self.provider}:{self.external_id}"

    @property
    def is_linked(self) -> bool:
        """Check if this identity is linked to a Reviewate user."""
        return self.user_id is not None

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<ProviderIdentity(id={self.id}, provider={self.provider}, username={self.username})>"
        )

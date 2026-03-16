"""SQLAlchemy database models for organizations."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.models.base import Base

if TYPE_CHECKING:
    from api.models.executions import Execution
    from api.models.identities import ProviderIdentity
    from api.models.linked_repositories import LinkedRepository
    from api.models.pull_requests import PullRequest
    from api.models.repositories import Repository


class Platform(StrEnum):
    """Git platform types."""

    GITHUB = "github"
    GITLAB = "gitlab"


class MemberRole(StrEnum):
    """Organization member roles."""

    ADMIN = "admin"
    MEMBER = "member"


class AutomaticReviewTrigger(StrEnum):
    """Automatic review trigger settings.

    Defines when code reviews are automatically triggered:
    - CREATION: Trigger when PR/MR is created
    - COMMIT: Trigger on each new commit
    - LABEL: Trigger when "reviewate" label is added
    - NONE: Disabled — never auto-trigger
    """

    CREATION = "creation"
    COMMIT = "commit"
    LABEL = "label"
    NONE = "none"


class Organization(Base):
    """Organization database model.

    Represents a team/organization that uses Reviewate (The Tenant).
    Each row represents a single organization or team that has installed the application.
    """

    __tablename__ = "organizations"
    __mapper_args__ = {"confirm_deleted_rows": False}
    # Primary key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4, index=True, name="id"
    )

    # Basic info
    name: Mapped[str] = mapped_column(String(255), name="name")
    external_org_id: Mapped[str] = mapped_column(
        String(255), index=True, name="external_org_id"
    )  # GitHub/GitLab org ID
    installation_id: Mapped[str] = mapped_column(
        String(255), index=True, name="installation_id"
    )  # App installation ID

    # Provider information
    provider: Mapped[str] = mapped_column(
        Enum("github", "gitlab", name="provider_enum"), nullable=False, name="provider"
    )  # github or gitlab
    provider_url: Mapped[str] = mapped_column(
        String(512), nullable=False, name="provider_url"
    )  # e.g., https://github.com or https://gitlab.com or custom GitLab instance
    avatar_url: Mapped[str | None] = mapped_column(
        String(512), nullable=True, name="avatar_url"
    )  # Organization avatar URL from GitHub/GitLab

    # GitLab Group Access Token (encrypted with AES-256-GCM)
    # Nullable: GitHub orgs use app installations, GitLab groups use this token
    gitlab_access_token_encrypted: Mapped[str | None] = mapped_column(
        String(512), nullable=True, name="gitlab_access_token_encrypted"
    )

    # Review settings
    automatic_review_trigger: Mapped[str] = mapped_column(
        String(20),
        default=AutomaticReviewTrigger.LABEL.value,
        nullable=False,
        name="automatic_review_trigger",
    )  # When to auto-trigger reviews: creation, commit, label, or none
    automatic_summary_trigger: Mapped[str] = mapped_column(
        String(20),
        default=AutomaticReviewTrigger.LABEL.value,
        nullable=False,
        name="automatic_summary_trigger",
    )  # When to auto-trigger summaries: creation, commit, label, or none

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
    members: Mapped[list[OrganizationMembership]] = relationship(
        "OrganizationMembership",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    repositories: Mapped[list[Repository]] = relationship(
        "Repository", back_populates="organization", cascade="all, delete-orphan"
    )
    pull_requests: Mapped[list[PullRequest]] = relationship(
        "PullRequest", back_populates="organization", cascade="all, delete-orphan"
    )
    executions: Mapped[list[Execution]] = relationship(
        "Execution", back_populates="organization", cascade="all, delete-orphan"
    )
    linked_repositories: Mapped[list[LinkedRepository]] = relationship(
        "LinkedRepository", back_populates="organization", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<Organization(id={self.id}, name={self.name})>"


class OrganizationMembership(Base):
    """Organization membership model.

    Links provider identities to organizations with roles and settings.
    A membership represents a team member in an organization.
    """

    __tablename__ = "organization_memberships"
    __mapper_args__ = {"confirm_deleted_rows": False}

    # Primary key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4, index=True, name="id"
    )

    # Foreign keys
    organization_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "organizations.id",
            ondelete="CASCADE",
            name="fk_organization_memberships_organization_id_organizations",
        ),
        index=True,
        name="organization_id",
    )
    provider_identity_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "provider_identities.id",
            ondelete="CASCADE",
            name="fk_organization_memberships_provider_identity_id",
        ),
        index=True,
        name="provider_identity_id",
    )

    # Membership details
    role: Mapped[str] = mapped_column(String(20), default=MemberRole.MEMBER.value, name="role")

    # Member settings
    reviewate_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, name="reviewate_enabled"
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

    # Unique constraint: one membership per identity per org
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "provider_identity_id",
            name="uq_org_membership_org_identity",
        ),
    )

    # Relationships
    provider_identity: Mapped[ProviderIdentity] = relationship("ProviderIdentity")
    organization: Mapped[Organization] = relationship("Organization", back_populates="members")

    @property
    def username(self) -> str | None:
        """Get username from linked identity."""
        return self.provider_identity.username if self.provider_identity else None

    @property
    def avatar_url(self) -> str | None:
        """Get avatar URL from linked identity."""
        return self.provider_identity.avatar_url if self.provider_identity else None

    @property
    def is_linked(self) -> bool:
        """Check if the member has a linked Reviewate user."""
        return self.provider_identity.is_linked if self.provider_identity else False

    def __repr__(self) -> str:
        """String representation."""
        return f"<OrganizationMembership(id={self.id}, org_id={self.organization_id}, identity_id={self.provider_identity_id}, role={self.role})>"

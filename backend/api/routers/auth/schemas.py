"""Request and response schemas for the auth API."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer

if TYPE_CHECKING:
    from api.models import User


class UserProfile(BaseModel):
    """User profile response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="User ID (UUID)")
    email: str | None = Field(description="User email")
    created_at: datetime = Field(description="Account creation timestamp")
    display_username: str = Field(description="Display username (first available)")

    # Onboarding
    onboarding_step: int | None = Field(
        None, description="Current onboarding tour step (None = not started)"
    )

    # Computed from identities
    github_username: str | None = Field(None, description="GitHub username (if linked)")
    gitlab_username: str | None = Field(None, description="GitLab username (if linked)")
    github_external_id: str | None = Field(None, description="GitHub user ID (if linked)")
    gitlab_external_id: str | None = Field(None, description="GitLab user ID (if linked)")
    google_external_id: str | None = Field(None, description="Google user ID (if linked)")

    @field_serializer("id")
    def serialize_id(self, value: UUID) -> str:
        """Convert UUID to string for JSON serialization."""
        return str(value)

    @classmethod
    def from_user(cls, user: User) -> UserProfile:
        """Create UserProfile from User model with identity data."""

        # Get identity data from linked identities
        github_identity = user.get_identity("github")
        gitlab_identity = user.get_identity("gitlab")
        google_identity = user.get_identity("google")

        return cls(
            id=user.id,
            email=user.email,
            created_at=user.created_at,
            display_username=user.display_username,
            onboarding_step=user.onboarding_step,
            github_username=github_identity.username if github_identity else None,
            gitlab_username=gitlab_identity.username if gitlab_identity else None,
            github_external_id=github_identity.external_id if github_identity else None,
            gitlab_external_id=gitlab_identity.external_id if gitlab_identity else None,
            google_external_id=google_identity.external_id if google_identity else None,
        )


class LogoutResponse(BaseModel):
    """Response for logout."""

    message: str = Field(description="Success message", default="Logged out successfully")


class SyncUserMembershipsMessage(BaseModel):
    """Message schema for user membership sync jobs.

    Published after OAuth login to trigger background sync of
    organization and repository memberships.
    """

    user_id: str = Field(description="User database ID (UUID)")
    provider: str = Field(description="OAuth provider: 'github' or 'gitlab'")
    access_token_encrypted: str = Field(description="Encrypted OAuth access token for API calls")
    external_user_id: str = Field(description="User's external ID on the provider platform")
    username: str | None = Field(None, description="Username on the provider platform")


class UpdateProfileRequest(BaseModel):
    """Request schema for updating user profile."""

    email: str | None = Field(None, description="New email address")
    onboarding_step: int | None = Field(None, description="Current onboarding tour step")


class UpdateProfileResponse(BaseModel):
    """Response after updating profile."""

    message: str = Field(default="Profile updated successfully")
    profile: UserProfile


class DisconnectProviderResponse(BaseModel):
    """Response after disconnecting a provider."""

    message: str = Field(default="Provider disconnected")
    profile: UserProfile

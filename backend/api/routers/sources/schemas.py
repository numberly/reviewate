"""Platform-agnostic schemas for sources management."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class OrganizationListItem(BaseModel):
    """Organization item in list response (platform-agnostic)."""

    id: UUID = Field(..., description="Unique organization ID in our system")
    name: str = Field(..., description="Organization display name")
    external_org_id: str = Field(
        ...,
        description="External ID from GitHub/GitLab (org ID, group ID, project ID)",
    )
    installation_id: str | None = Field(
        None,
        description="GitHub App installation ID, or GitLab token hash",
    )
    provider: Literal["github", "gitlab"] = Field(
        ...,
        description="Git provider type (github or gitlab)",
    )
    avatar_url: str | None = Field(
        None,
        description="Organization avatar URL from GitHub/GitLab",
    )
    created_at: datetime = Field(
        ...,
        description="When this organization was added to Reviewate",
    )
    role: Literal["admin", "member"] = Field(
        ...,
        description="Current user's role in this organization",
    )


class InstallAppResponse(BaseModel):
    """Response containing the app installation URL."""

    installation_url: str = Field(
        ...,
        description="URL to redirect user for GitHub/GitLab App installation",
        examples=["https://github.com/apps/reviewate-dev/installations/new"],
    )


class DeleteOrganizationResponse(BaseModel):
    """Response for organization deletion."""

    message: str = Field(description="Success message")
    organization_id: str = Field(description="Deleted organization ID (UUID)")

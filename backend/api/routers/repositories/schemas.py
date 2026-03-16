"""Request and response schemas for the repositories API."""

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class AutomaticReviewTriggerEnum(StrEnum):
    """Automatic review trigger options for API validation."""

    CREATION = "creation"
    COMMIT = "commit"
    LABEL = "label"
    NONE = "none"


class RepositoryListItem(BaseModel):
    """Repository item in list response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Repository ID (UUID)")
    organization_id: UUID = Field(description="Organization ID (UUID)")
    external_repo_id: str = Field(description="GitHub/GitLab repository ID")
    platform: str = Field(description="Git platform (github or gitlab)", alias="provider")
    name: str = Field(description="Repository name")
    web_url: str = Field(description="Full URL to the repository")
    avatar_url: str | None = Field(None, description="Repository avatar URL (owner's avatar)")
    created_at: datetime = Field(description="Creation timestamp")

    @field_serializer("id", "organization_id")
    def serialize_uuid(self, value: UUID) -> str:
        """Convert UUID to string for JSON serialization."""
        return str(value)


class DeleteRepositoryResponse(BaseModel):
    """Response for repository deletion."""

    message: str = Field(description="Success message")
    repository_id: str = Field(description="Deleted repository ID (UUID)")


class RepositoryEventMessage(BaseModel):
    """Message schema for repository SSE events.

    Published when a repository is created, updated, or deleted.
    Consumed by SSE handler to broadcast to connected dashboard clients.
    """

    organization_id: str = Field(
        description="Organization ID that owns the repository",
    )

    action: str = Field(
        description="Action type: created, updated, or deleted",
    )

    repository: dict[str, Any] = Field(
        description="Repository data",
    )

    timestamp: str | None = Field(
        default=None,
        description="Event timestamp (ISO format)",
    )


class RepositorySettingsUpdate(BaseModel):
    """Request schema for updating repository settings.

    Pass null to clear an override and inherit from organization.
    Omit a field to leave it unchanged.
    """

    automatic_review_trigger: AutomaticReviewTriggerEnum | None = Field(
        default=None,
        description="When to auto-trigger. Set to null to inherit from organization.",
    )
    automatic_summary_trigger: AutomaticReviewTriggerEnum | None = Field(
        default=None,
        description="When to auto-trigger summaries. Set to null to inherit from organization.",
    )


class RepositorySettings(BaseModel):
    """Response schema for repository settings (raw values before inheritance)."""

    model_config = ConfigDict(from_attributes=True)

    automatic_review_trigger: str | None = Field(
        description="Trigger setting (null means inherits from organization)",
    )
    automatic_summary_trigger: str | None = Field(
        description="Summary trigger (null means inherits from organization)",
    )

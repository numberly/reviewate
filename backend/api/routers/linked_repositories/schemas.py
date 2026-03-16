"""Pydantic schemas for linked repositories API."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LinkedRepositoryCreate(BaseModel):
    """Request schema for creating a linked repository."""

    url: str = Field(
        description="Full repository URL (e.g., 'https://github.com/owner/repo')",
        max_length=1024,
    )
    branch: str = Field(
        description="Branch name",
        max_length=255,
    )


class LinkedRepositoryResponse(BaseModel):
    """Response schema for a linked repository."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Linked repository ID (UUID)")
    linked_provider: str = Field(description="Provider type: 'github' or 'gitlab'")
    linked_provider_url: str = Field(description="Provider URL")
    linked_repo_path: str = Field(description="Repository path (e.g., 'owner/repo')")
    linked_branch: str | None = Field(description="Specific branch (null = default branch)")
    display_name: str | None = Field(description="Display name for UI")
    organization_id: UUID | None = Field(description="Organization ID if org-level link")
    repository_id: UUID | None = Field(description="Repository ID if repo-level link")


class DeleteLinkedRepositoryResponse(BaseModel):
    """Response schema for deleting a linked repository."""

    message: str = Field(description="Success message")
    linked_repository_id: str = Field(description="ID of the deleted linked repository")

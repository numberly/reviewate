"""Schemas for GitLab sources endpoints."""

from datetime import datetime

from pydantic import BaseModel, Field


class AddGitLabSourceRequest(BaseModel):
    """Request schema for adding a GitLab source."""

    access_token: str = Field(description="GitLab Personal Access Token (group or project level)")
    provider_url: str = Field(
        default="https://gitlab.com",
        description="GitLab instance URL (default: https://gitlab.com)",
    )


class GitLabSourceResponse(BaseModel):
    """Response schema for GitLab source creation."""

    source_type: str = Field(description="Type of source: 'group' or 'project'")
    source_id: str = Field(description="ID of created Organization or Repository")
    source_name: str = Field(description="Name of the group or project")
    membership_created: bool = Field(description="Whether membership was created for the user")
    created_at: datetime = Field(description="Timestamp of creation")


# Queue message schemas for background sync jobs


class GitLabSyncGroupMessage(BaseModel):
    """Message schema for GitLab group sync jobs.

    Published to trigger background sync of merge requests
    for all repositories in a GitLab group.
    """

    organization_id: str = Field(
        description="Organization database ID (UUID)",
    )

    repository_ids: list[str] = Field(
        description="List of repository database IDs (UUIDs) to sync",
    )


class GitLabSyncRepositoryMRsMessage(BaseModel):
    """Message schema for GitLab repository MR sync jobs.

    Published for each repository to sync its merge requests.
    """

    repository_id: str = Field(
        description="Repository database ID (UUID)",
    )

    organization_id: str = Field(
        description="Organization database ID (UUID)",
    )


class GitLabSyncGroupRepositoriesMessage(BaseModel):
    """Message schema for GitLab group repository sync jobs.

    Published to trigger background sync of all repositories
    in a GitLab group (fetch from API + create in DB).
    """

    organization_id: str = Field(
        description="Organization database ID (UUID)",
    )

    group_id: str = Field(
        description="GitLab group ID to fetch projects from",
    )

    user_id: str = Field(
        description="User ID of the installer (for creating repo memberships)",
    )

    encrypted_token: str | None = Field(
        default=None,
        description="Encrypted access token to store on repos (for subgroup tokens)",
    )

    store_token_on_repos: bool = Field(
        default=False,
        description="When True, store the encrypted token on each repo instead of the org",
    )


class GitLabSyncMembersMessage(BaseModel):
    """Message schema for GitLab group member sync jobs.

    Published after a GitLab group token is added to trigger
    background sync of all group members.
    """

    organization_id: str = Field(
        description="Organization database ID (UUID)",
    )

    group_id: str = Field(
        description="GitLab group ID",
    )

    encrypted_token: str | None = Field(
        default=None,
        description="Encrypted access token override (for subgroup tokens)",
    )

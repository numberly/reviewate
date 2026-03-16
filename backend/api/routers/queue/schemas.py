"""Message schemas for FastStream queues."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class LinkedRepoMessage(BaseModel):
    """Schema for a linked repository in job messages."""

    provider: str = Field(description="Provider type: github or gitlab")
    provider_url: str = Field(description="Provider URL (e.g., https://github.com)")
    repo_path: str = Field(description="Repository path (e.g., owner/repo)")
    branch: str | None = Field(default=None, description="Specific branch (null = default)")
    display_name: str | None = Field(default=None, description="Display name for UI")
    name: str = Field(description="Short identifier used in namespaced paths [name]/...")


class ReviewJobMessage(BaseModel):
    """Message schema for code review jobs.

    This message is published to the review queue when a PR/MR
    needs to be reviewed.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "repository_id": 1,
                "pull_request_id": 42,
                "pull_request_number": 123,
                "platform": "github",
                "organization": "reviewate",
                "repository": "reviewate",
                "source_branch": "feature/faststream",
                "target_branch": "main",
                "commit_sha": "abc123def456",
                "workflow": "review",
                "triggered_by": "user@example.com",
                "triggered_at": "2025-01-15T12:00:00Z",
                "context": {
                    "labels": ["bug", "urgent"],
                    "milestone": "v1.0",
                },
                "linked_repos": [],
            }
        }
    )

    # Job identification
    job_id: str = Field(
        description="Unique job identifier (UUID)",
    )

    # Organization information
    organization_id: str = Field(
        description="Organization database ID (UUID)",
    )

    # Pull request information
    repository_id: str = Field(
        description="Repository database ID (UUID)",
    )

    pull_request_id: str = Field(
        description="Pull request database ID (UUID)",
    )

    pull_request_number: int = Field(
        description="Pull request number (from Git platform)",
    )

    # Platform information
    platform: str = Field(
        description="Git platform (github, gitlab)",
    )

    organization: str = Field(
        description="Repository organization/owner",
    )

    repository: str = Field(
        description="Repository name",
    )

    # Git references
    source_branch: str = Field(
        description="Source branch name",
    )

    target_branch: str = Field(
        description="Target branch name",
    )

    commit_sha: str = Field(
        description="Latest commit SHA to review",
    )

    # Review configuration
    workflow: str = Field(
        default="review",
        description="Workflow to execute (review, summarize)",
    )

    # Metadata
    triggered_by: str = Field(
        description="User who triggered the review",
    )

    triggered_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the review was triggered",
    )

    # Additional context
    context: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context for the review",
    )

    # Linked repositories for cross-repo context during review
    linked_repos: list[LinkedRepoMessage] = Field(
        default_factory=list,
        description="Linked repositories to include in code exploration",
    )

    # Team guidelines from feedback summarization
    team_guidelines: str | None = Field(
        default=None,
        description="Natural language team guidelines from feedback summarization",
    )


class ExecutionStatusMessage(BaseModel):
    """Message schema for execution status updates.

    This message is published by the container watcher when a container
    status changes (started, completed, failed).
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "execution_id": "550e8400-e29b-41d4-a716-446655440000",
                "container_id": "abc123def456",
                "status": "completed",
                "exit_code": 0,
                "error_message": None,
                "result": {"comments": [], "metrics": {}},
                "timestamp": "2025-01-15T12:05:30Z",
            }
        }
    )

    execution_id: str = Field(
        description="Execution database ID (UUID)",
    )

    container_id: str | None = Field(
        default=None,
        description="Container/pod ID",
    )

    status: str = Field(
        description="Execution status (processing, completed, failed)",
    )

    exit_code: int | None = Field(
        default=None,
        description="Container exit code (if exited)",
    )

    error_message: str | None = Field(
        default=None,
        description="Error message (if failed)",
    )

    error_type: str | None = Field(
        default=None,
        description="Standardized error type (if failed)",
    )

    result: dict[str, Any] | None = Field(
        default=None,
        description="Parsed result from container logs",
    )

    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the status change occurred",
    )

"""Request and response schemas for the pull requests API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator

ExecutionStatusType = str  # 'queued' | 'processing' | 'completed' | 'failed' | 'cancelled'


class StatChange(BaseModel):
    """Week-over-week change for a dashboard stat."""

    percentage: float | None = Field(None, description="Percentage change (e.g. 5.0 for +5%)")
    trend: Literal["up", "down", "neutral"] = Field(description="Trend direction")


class DashboardStatsResponse(BaseModel):
    """Response schema for dashboard statistics."""

    active_repos: int = Field(description="Repos with >= 1 completed review in last 7 days")
    active_repos_change: StatChange = Field(description="Week-over-week change for active repos")
    avg_review_time_seconds: float | None = Field(
        None, description="Average review time in seconds (null if no data)"
    )
    avg_review_time_change: StatChange = Field(
        description="Week-over-week change for avg review time"
    )
    prs_reviewed: int = Field(description="Distinct PRs reviewed in last 7 days")
    prs_reviewed_change: StatChange = Field(description="Week-over-week change for PRs reviewed")


class PullRequestDetail(BaseModel):
    """Detailed pull request information (base for list item)."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(description="Pull request ID (UUID)")
    organization_id: str = Field(description="Organization ID (UUID)")
    repository_id: str = Field(description="Repository ID (UUID)")
    pr_number: int = Field(description="Pull request number")
    external_pr_id: str = Field(description="External PR ID from provider")
    title: str = Field(description="Pull request title")
    author: str = Field(description="Pull request author username")
    state: str = Field(description="Pull request state (open, closed, merged)")
    head_branch: str = Field(description="Source branch")
    base_branch: str = Field(description="Target branch")
    head_sha: str = Field(description="Latest commit SHA on head branch")
    pr_url: str = Field(description="Full URL to the pull request")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")

    author_reviewate_disabled: bool = Field(
        default=False,
        description="Whether the PR author has reviews disabled",
    )

    @field_validator("id", "organization_id", "repository_id", mode="before")
    @classmethod
    def _coerce_uuid(cls, v: object) -> object:
        """Auto-convert UUID objects to str for ORM compatibility."""
        return str(v) if v is not None else v

    @classmethod
    def from_pr(cls, pr: Any, **kwargs: Any) -> Self:
        """Build from a PullRequest ORM object, with optional field overrides."""
        instance = cls.model_validate(pr, from_attributes=True)
        if kwargs:
            instance = instance.model_copy(update=kwargs)
        return instance


class PullRequestListItem(PullRequestDetail):
    """Pull request item in list response, with latest execution info."""

    latest_execution_id: str | None = Field(None, description="Latest execution ID (UUID) or None")
    latest_execution_status: ExecutionStatusType | None = Field(
        None, description="Latest execution status or None"
    )
    latest_execution_created_at: datetime | None = Field(
        None, description="Latest execution creation time or None"
    )
    latest_execution_error_type: str | None = Field(
        None, description="Error type if latest execution failed"
    )
    latest_execution_error_detail: str | None = Field(
        None, description="Technical error detail if latest execution failed"
    )

    @classmethod
    def from_pr_with_execution(cls, pr: Any, execution: Any | None = None, **kwargs: Any) -> Self:
        """Build from a PullRequest ORM object and optional Execution."""
        if execution:
            kwargs.update(
                {
                    "latest_execution_id": str(execution.id),
                    "latest_execution_status": execution.status,
                    "latest_execution_created_at": execution.created_at,
                    "latest_execution_error_type": execution.error_type,
                    "latest_execution_error_detail": execution.error_detail,
                }
            )
        return cls.from_pr(pr, **kwargs)


class TriggerReviewRequest(BaseModel):
    """Request schema for triggering a review."""

    commit_sha: str = Field(description="Commit SHA to review", min_length=7, max_length=40)


class TriggerReviewResponse(BaseModel):
    """Response schema for triggered review."""

    execution_id: str = Field(description="Execution ID (UUID)")
    pull_request_id: str = Field(description="Pull request ID (UUID)")
    status: ExecutionStatusType = Field(description="Execution status")
    commit_sha: str = Field(description="Commit SHA being reviewed")
    created_at: datetime = Field(description="Execution creation timestamp")


class PullRequestEventMessage(BaseModel):
    """Message schema for pull request SSE events.

    Published when a PR is created/updated or execution status changes.
    Consumed by SSE handler to broadcast to connected dashboard clients.
    """

    pull_request_id: str = Field(
        description="Pull request ID (UUID)",
    )

    action: str = Field(
        description="Action type: created, updated, execution_created, execution_status_changed",
    )

    state: str | None = Field(
        default=None,
        description="PR state (open, closed, merged) - present on lifecycle events",
    )

    organization_id: str | None = Field(
        default=None,
        description="Organization ID (UUID)",
    )

    repository_id: str | None = Field(
        default=None,
        description="Repository ID (UUID)",
    )

    latest_execution_id: str | None = Field(
        default=None,
        description="Latest execution ID (UUID)",
    )

    latest_execution_status: str | None = Field(
        default=None,
        description="Latest execution status",
    )

    latest_execution_created_at: str | None = Field(
        default=None,
        description="Latest execution creation timestamp (ISO format)",
    )

    updated_at: str | None = Field(
        default=None,
        description="Update timestamp (ISO format)",
    )

    workflow: str | None = Field(
        default=None,
        description="Workflow type (review, summarize) - used by frontend to filter non-review events",
    )

    error_type: str | None = Field(
        default=None,
        description="Standardized error type (if execution failed)",
    )

    error_detail: str | None = Field(
        default=None,
        description="Technical error detail (if execution failed, controlled by expose_error_details config)",
    )

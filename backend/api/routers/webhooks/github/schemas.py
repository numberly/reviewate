"""GitHub webhook payload schemas."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class GitHubInstallationAction(StrEnum):
    """GitHub App installation webhook actions."""

    CREATED = "created"
    DELETED = "deleted"
    SUSPEND = "suspend"
    UNSUSPEND = "unsuspend"
    NEW_PERMISSIONS_ACCEPTED = "new_permissions_accepted"


class GitHubInstallationRepositoriesAction(StrEnum):
    """GitHub App installation repositories webhook actions."""

    ADDED = "added"
    REMOVED = "removed"


class GitHubAppInstallationEvent(BaseModel):
    """GitHub App installation webhook payload."""

    action: str = Field(description="Event action (created, deleted, etc.)")
    installation: dict[str, Any] = Field(description="Installation object")
    repositories: list[dict[str, Any]] | None = Field(
        description="Repositories affected", default=None
    )
    sender: dict[str, Any] = Field(description="User who triggered the event")


class GitHubAppInstallationRepositoriesEvent(BaseModel):
    """GitHub App installation_repositories webhook payload."""

    action: str = Field(description="Event action (added, removed)")
    installation: dict[str, Any] = Field(description="Installation object")
    repositories_added: list[dict[str, Any]] | None = Field(
        description="Repositories that were added", default=None
    )
    repositories_removed: list[dict[str, Any]] | None = Field(
        description="Repositories that were removed", default=None
    )
    sender: dict[str, Any] = Field(description="User who triggered the event")


class GitHubPullRequestEvent(BaseModel):
    """GitHub pull request webhook payload."""

    action: str = Field(description="Event action (opened, synchronize, etc.)")
    number: int = Field(description="Pull request number")
    pull_request: dict[str, Any] = Field(description="Pull request object")
    repository: dict[str, Any] = Field(description="Repository object")
    installation: dict[str, Any] | None = Field(description="Installation object", default=None)
    sender: dict[str, Any] = Field(description="User who triggered the event")
    label: dict[str, Any] | None = Field(
        description="Label added/removed (on labeled/unlabeled actions)", default=None
    )


# Queue message schemas for background sync jobs


class GitHubSyncInstallationMessage(BaseModel):
    """Message schema for GitHub installation sync jobs.

    Published after a GitHub App installation webhook to trigger
    background sync of all repositories.
    """

    installation_id: str = Field(
        description="GitHub App installation ID",
    )

    sender_github_id: str | None = Field(
        default=None,
        description="GitHub user ID who installed the app",
    )


class GitHubSyncRepositoryPRsMessage(BaseModel):
    """Message schema for GitHub repository PR sync jobs.

    Published for each repository to sync its pull requests
    after installation sync.
    """

    repository_id: str = Field(
        description="Repository database ID (UUID)",
    )

    installation_id: str = Field(
        description="GitHub App installation ID",
    )

    owner: str = Field(
        description="GitHub repository owner/organization",
    )

    repo_name: str = Field(
        description="GitHub repository name",
    )


class GitHubSyncMembersMessage(BaseModel):
    """Message schema for GitHub organization member sync jobs.

    Published after a GitHub App installation webhook to trigger
    background sync of all organization members.
    """

    installation_id: str = Field(
        description="GitHub App installation ID",
    )

    organization_id: str = Field(
        description="Organization database ID (UUID)",
    )

    org_name: str = Field(
        description="GitHub organization login name",
    )


# Feedback event schemas


class GitHubIssueCommentEvent(BaseModel):
    """GitHub issue_comment webhook payload.

    Triggered when a comment is created on an issue or PR.
    Used to capture replies to Reviewate review comments.
    """

    action: str = Field(description="Event action (created, edited, deleted)")
    issue: dict[str, Any] = Field(description="Issue or PR object")
    comment: dict[str, Any] = Field(description="Comment object")
    repository: dict[str, Any] = Field(description="Repository object")
    installation: dict[str, Any] | None = Field(description="Installation object", default=None)
    sender: dict[str, Any] = Field(description="User who triggered the event")


class GitHubPullRequestReviewCommentEvent(BaseModel):
    """GitHub pull_request_review_comment webhook payload.

    Triggered when a comment on a PR review is created/edited/deleted.
    Used to capture reactions on Reviewate review comments.
    """

    action: str = Field(description="Event action (created, edited, deleted)")
    comment: dict[str, Any] = Field(description="Review comment object")
    pull_request: dict[str, Any] = Field(description="Pull request object")
    repository: dict[str, Any] = Field(description="Repository object")
    installation: dict[str, Any] | None = Field(description="Installation object", default=None)
    sender: dict[str, Any] = Field(description="User who triggered the event")


class GitHubPullRequestReviewEvent(BaseModel):
    """GitHub pull_request_review webhook payload.

    Triggered when a review is submitted, edited, or dismissed.
    Used to capture dismissed Reviewate reviews.
    """

    action: str = Field(description="Event action (submitted, edited, dismissed)")
    review: dict[str, Any] = Field(description="Review object")
    pull_request: dict[str, Any] = Field(description="Pull request object")
    repository: dict[str, Any] = Field(description="Repository object")
    installation: dict[str, Any] | None = Field(description="Installation object", default=None)
    sender: dict[str, Any] = Field(description="User who triggered the event")


class FeedbackSignalMessage(BaseModel):
    """Message schema for feedback signal processing.

    Published when user feedback is detected (thumbs-down, reply, dismissed review)
    to be processed by the feedback consumer.
    """

    organization_id: str = Field(description="Organization database ID (UUID)")
    repository_id: str | None = Field(
        default=None,
        description="Repository database ID (UUID)",
    )
    pull_request_id: str | None = Field(
        default=None,
        description="Pull request database ID (UUID)",
    )
    feedback_type: str = Field(description="Type: thumbs_down, reply_comment, dismissed_review")
    review_comment_body: str = Field(description="Original review comment")
    file_path: str | None = Field(default=None, description="File path")
    code_snippet: str | None = Field(default=None, description="Code snippet")
    user_reply: str | None = Field(default=None, description="User's reply text")
    platform: str = Field(default="github", description="Platform")
    pr_author: str | None = Field(default=None, description="PR author")
    commenter: str | None = Field(default=None, description="User who gave feedback")


__all__ = [
    "GitHubInstallationAction",
    "GitHubInstallationRepositoriesAction",
    "GitHubAppInstallationEvent",
    "GitHubAppInstallationRepositoriesEvent",
    "GitHubPullRequestEvent",
    "GitHubSyncInstallationMessage",
    "GitHubSyncRepositoryPRsMessage",
    "GitHubSyncMembersMessage",
    # Feedback events
    "GitHubIssueCommentEvent",
    "GitHubPullRequestReviewCommentEvent",
    "GitHubPullRequestReviewEvent",
    "FeedbackSignalMessage",
]

"""GitLab webhook payload schemas."""

from typing import Any

from pydantic import BaseModel, Field


class GitLabMergeRequestEvent(BaseModel):
    """GitLab merge request webhook payload."""

    object_kind: str = Field(description="Event type (merge_request)")
    event_type: str | None = Field(description="Event action (merge_request)", default=None)
    user: dict[str, Any] = Field(description="User who triggered the event")
    project: dict[str, Any] = Field(description="Project object")
    object_attributes: dict[str, Any] = Field(description="Merge request object")
    repository: dict[str, Any] | None = Field(description="Repository object", default=None)
    changes: dict[str, Any] | None = Field(
        description="Changes made to the MR (includes labels for update action)",
        default=None,
    )
    labels: list[dict[str, Any]] | None = Field(
        description="Current labels on the MR",
        default=None,
    )


class GitLabNoteEvent(BaseModel):
    """GitLab note (comment) webhook payload.

    Used for capturing comments on MRs and award emoji (reactions).
    """

    object_kind: str = Field(description="Event type (note)")
    event_type: str | None = Field(description="Event action (note)", default=None)
    user: dict[str, Any] = Field(description="User who triggered the event")
    project: dict[str, Any] = Field(description="Project object")
    object_attributes: dict[str, Any] = Field(description="Note object attributes")
    merge_request: dict[str, Any] | None = Field(
        description="Merge request (if comment is on MR)", default=None
    )
    repository: dict[str, Any] | None = Field(description="Repository object", default=None)


class GitLabFeedbackSignalMessage(BaseModel):
    """Message schema for GitLab feedback signal processing."""

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
    platform: str = Field(default="gitlab", description="Platform")
    pr_author: str | None = Field(default=None, description="MR author")
    commenter: str | None = Field(default=None, description="User who gave feedback")

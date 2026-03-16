"""Shared schema types for repository handlers."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Review[PlatformReviewComment: BaseModel](BaseModel):
    """Generic review container — Review[GitHubReviewComment] or Review[GitLabReviewComment]."""

    comments: list[PlatformReviewComment]


class PostFailure(BaseModel):
    """A single comment that failed to post."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    comment: BaseModel
    error: str


class PostResult(BaseModel):
    """Result of a posting attempt."""

    posted: int = 0
    failed: list[PostFailure] = []

    @property
    def all_posted(self) -> bool:
        return len(self.failed) == 0 and self.posted > 0

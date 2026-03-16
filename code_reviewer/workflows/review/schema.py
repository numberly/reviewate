"""Review workflow schema types."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from code_reviewer.adaptors.repository.schema import Review


class FilterResult(BaseModel):
    """Result from filter agents (dedup, fact-check) — indices of comments to keep."""

    model_config = ConfigDict(extra="forbid")

    keep_indices: list[int]


class StyleResult(BaseModel):
    """Result from StyleAgent — reformatted body strings aligned by input index."""

    model_config = ConfigDict(extra="forbid")

    bodies: list[str]


LGTM_BODY = "LGTM, good job 🍾 👏"


class LgtmComment(BaseModel):
    """Minimal model for posting the LGTM comment via handler."""

    body: str = LGTM_BODY


class ReviewResult(BaseModel):
    """Result from the review agent, wrapping a typed Review + cost."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    review: Review
    cost_usd: float | None = None

    @property
    def comments(self) -> list:
        return self.review.comments

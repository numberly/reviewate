"""GitHub review comment schema for LLM output."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class GitHubReviewComment(BaseModel):
    """GitHub review comment format for LLM output.

    This schema is used by agents to generate structured review comments.
    The posting layer will add commit_id and other metadata when posting.
    """

    model_config = ConfigDict(extra="forbid")

    path: Annotated[
        str | None,
        Field(
            description=(
                "Relative file path from the diff header (e.g. 'src/main.rs'). "
                "Required for inline comments."
            )
        ),
    ] = None
    body: Annotated[str, Field(description="The review comment body (supports markdown)")]
    line: Annotated[
        int | None,
        Field(
            description=(
                "The line number where the comment should appear. "
                "Read directly from the diff: added lines show '      N   :+' (use N), "
                "deleted lines show 'N         :-' (use N). "
                "Required for inline comments — never leave as null."
            )
        ),
    ] = None
    side: Annotated[
        str | None,
        Field(
            description=(
                "Which side of the diff: RIGHT for added/modified lines (+), "
                "LEFT for deleted lines (-). Defaults to RIGHT."
            )
        ),
    ] = None

"""GitLab review comment schema for LLM output."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class GitLabReviewComment(BaseModel):
    """GitLab review comment format for LLM output.

    This schema is used by agents to generate structured review comments.
    The posting layer will add SHAs and other metadata when posting.
    """

    model_config = ConfigDict(extra="forbid")

    body: Annotated[str, Field(description="The review comment body (supports markdown)")]
    new_path: Annotated[
        str | None,
        Field(
            description=(
                "Relative file path from the diff header (e.g. 'src/main.rs'). "
                "Required for inline comments on added/modified lines."
            )
        ),
    ] = None
    new_line: Annotated[
        int | None,
        Field(
            description=(
                "Line number in the new file. Read directly from the diff: "
                "added lines show '      N   :+' (use N). "
                "Required for inline comments on new code — never leave as null."
            )
        ),
    ] = None
    old_path: Annotated[
        str | None,
        Field(
            description=(
                "Old file path (for renamed/deleted files). "
                "Only needed when commenting on deleted lines."
            )
        ),
    ] = None
    old_line: Annotated[
        int | None,
        Field(
            description=(
                "Line number in the old file. Read directly from the diff: "
                "deleted lines show 'N         :-' (use N). "
                "Only needed when commenting on deleted code."
            )
        ),
    ] = None

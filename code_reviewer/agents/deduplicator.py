"""DedupAgent — filters findings already covered by existing PR/MR discussions."""

from __future__ import annotations

from code_reviewer.agents.base import BaseAgent
from code_reviewer.workflows.review.schema import FilterResult


class DedupAgent(BaseAgent):
    """Deduplication agent that filters findings already covered by human comments.

    Compares AI findings against existing PR/MR discussions and removes
    duplicates. Discussions are baked into the prompt via template_vars.
    """

    prompt_file = "dedup.md"
    permission_mode = "bypassPermissions"
    allowed_tools: list[str] = []
    max_turns = 1
    output_schema = FilterResult

    def __init__(
        self,
        *,
        model: str = "haiku",
        discussions: list[dict] | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(
            template_vars={"discussions": discussions or []},
            **kwargs,  # type: ignore[arg-type]
        )
        self.model = model

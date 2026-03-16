"""StyleAgent — reformats comment bodies into concise, scannable markdown."""

from __future__ import annotations

from code_reviewer.agents.base import BaseAgent
from code_reviewer.workflows.review.schema import StyleResult


class StyleAgent(BaseAgent):
    """Formatter that rewrites verbose comment bodies into concise markdown.

    Only reformats the body text — path/line/side are preserved by the pipeline.
    Returns StyleResult(bodies=[...]) aligned by input index.
    """

    prompt_file = "style.md"
    permission_mode = "bypassPermissions"
    allowed_tools: list[str] = []
    max_turns = 1
    output_schema = StyleResult

    def __init__(
        self,
        *,
        model: str = "haiku",
        platform: str = "github",
        **kwargs: object,
    ) -> None:
        super().__init__(
            template_vars={"platform": platform},
            **kwargs,  # type: ignore[arg-type]
        )
        self.model = model

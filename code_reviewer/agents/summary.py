"""SummarizerAgent — generates PR/MR summary bullet points."""

from __future__ import annotations

from code_reviewer.agents.base import BaseAgent
from code_reviewer.workflows.summary.schema import SummaryOutput


class SummarizerAgent(BaseAgent):
    """Generates a bullet-point summary of PR/MR changes.

    Receives PR description + diff via system prompt prefix and
    linked issue context in the user prompt. Returns structured
    SummaryOutput with a description field.
    """

    prompt_file = "summarizer.md"
    permission_mode = "bypassPermissions"
    allowed_tools: list[str] = []
    max_turns = 1
    output_schema = SummaryOutput

    def __init__(
        self,
        *,
        model: str = "haiku",
        pr_description: str = "",
        diff: str = "",
        issue_context: str = "",
        **kwargs: object,
    ) -> None:
        super().__init__(
            template_vars={
                "pr_description": pr_description,
                "diff": diff,
                "issue_context": issue_context,
            },
            **kwargs,  # type: ignore[arg-type]
        )
        self.model = model

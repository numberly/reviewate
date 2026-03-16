"""SummaryParserAgent — condenses and refines a raw summary."""

from __future__ import annotations

from code_reviewer.agents.base import BaseAgent
from code_reviewer.workflows.summary.schema import ParsedSummaryOutput


class SummaryParserAgent(BaseAgent):
    """Refines a raw SummaryOutput into a more concise description.

    Receives the raw summary JSON in the user prompt and returns
    a condensed ParsedSummaryOutput.
    """

    prompt_file = "summary-parser.md"
    permission_mode = "bypassPermissions"
    allowed_tools: list[str] = []
    max_turns = 1
    output_schema = ParsedSummaryOutput

    def __init__(self, *, model: str = "haiku", **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self.model = model

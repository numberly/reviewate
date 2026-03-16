"""SynthesizerAgent — merges and deduplicates findings from parallel reviewers."""

from __future__ import annotations

from pydantic import BaseModel

from code_reviewer.agents.base import BaseAgent


class SynthesizerAgent(BaseAgent):
    """Merges findings from multiple parallel review agents.

    Removes exact duplicates, resolves contradictions, and produces
    a single prioritized list of findings.
    """

    prompt_file = "synthesize.md"
    permission_mode = "bypassPermissions"
    allowed_tools: list[str] = []
    max_turns = 1

    def __init__(
        self,
        *,
        model: str = "haiku",
        output_schema: type[BaseModel] | None = None,
        platform: str = "github",
        pr_description: str = "",
        diff: str = "",
        issue_context: str = "",
        **kwargs: object,
    ) -> None:
        super().__init__(
            template_vars={
                "platform": platform,
                "pr_description": pr_description,
                "diff": diff,
                "issue_context": issue_context,
            },
            **kwargs,  # type: ignore[arg-type]
        )
        self.model = model
        self.output_schema = output_schema

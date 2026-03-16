"""FactCheckAgent — verifies review findings against actual code."""

from __future__ import annotations

from code_reviewer.agents.base import BaseAgent
from code_reviewer.workflows.review.schema import FilterResult


class FactCheckAgent(BaseAgent):
    """Fact checker that verifies findings against actual code.

    Reads the codebase to confirm or discard each finding. Default verdict
    is DISCARD — only keeps findings with concrete code evidence.
    """

    prompt_file = "fact-check.md"
    permission_mode = "bypassPermissions"
    allowed_tools = ["Skill", "Read", "Grep", "Glob", "Bash"]
    disallowed_tools = ["Agent", "Task"]
    setting_sources = ["project"]
    output_schema = FilterResult
    max_turns = 25

    def __init__(
        self,
        *,
        model: str = "sonnet",
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

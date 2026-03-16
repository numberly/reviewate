"""AnalyzeAgent — code review analyzer that explores the codebase and finds bugs."""

from __future__ import annotations

from pydantic import BaseModel

from code_reviewer.agents.base import BaseAgent


class AnalyzeAgent(BaseAgent):
    """Code review analyzer that explores the codebase and finds bugs.

    Given a PR target and repo path, reads the diff, explores surrounding code,
    and reports confirmed bugs with file/line references.
    """

    prompt_file = "analyze.md"
    permission_mode = "bypassPermissions"
    allowed_tools = ["Skill", "Read", "Grep", "Glob", "Bash"]
    disallowed_tools = ["Agent", "Task"]
    setting_sources = ["project"]
    max_turns = 12

    def __init__(
        self,
        *,
        model: str = "sonnet",
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

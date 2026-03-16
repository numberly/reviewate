"""IssueExplorerAgent — discovers and fetches linked issues from PR/MR description."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from code_reviewer.agents.base import BaseAgent


class IssueExplorerOutput(BaseModel):
    """Structured output from issue explorer — context + issue URLs."""

    model_config = ConfigDict(extra="forbid")

    context: str
    issue_refs: list[str] = []


class IssueExplorerAgent(BaseAgent):
    """Discovers linked issues from PR/MR description and fetches their context.

    Uses Bash to call gh/glab CLI to view the PR and fetch linked issues.
    Returns a summary of requirements, acceptance criteria, and discussion
    context for downstream agents.
    """

    prompt_file = "issue-explorer.md"
    permission_mode = "bypassPermissions"
    allowed_tools = ["Bash"]
    output_schema = IssueExplorerOutput

    def __init__(
        self,
        *,
        model: str = "haiku",
        platform: str = "github",
        repo: str = "",
        pr_description: str = "",
        **kwargs: object,
    ) -> None:
        super().__init__(
            template_vars={
                "platform": platform,
                "repo": repo,
                "pr_description": pr_description,
            },
            **kwargs,  # type: ignore[arg-type]
        )
        self.model = model

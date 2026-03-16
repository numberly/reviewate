"""RunContext — shared state for a single run invocation."""

from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel, ConfigDict, Field

from code_reviewer.adaptors.repository import RepositoryHandler
from code_reviewer.output import ProgressTracker


class RunContext(BaseModel):
    """Shared state for a single run invocation."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    handler: RepositoryHandler
    repo: str
    pr: str
    workspace: str
    agent_env: dict[str, str]
    sub_env: dict[str, str]
    system_extra: str
    review_model: str
    utility_model: str
    dry_run: bool
    debug: bool
    tracker: ProgressTracker | None = None
    pr_body: str = ""
    diff_text: str = ""
    total_cost: float = 0.0
    total_usage: dict[str, int] = Field(default_factory=dict)
    agent_usages: list[tuple[str, dict[str, int]]] = Field(default_factory=list)
    result_data: dict = Field(default_factory=lambda: {"status": "success", "workflows": []})
    review_comments: list = Field(default_factory=list)
    summary_body: str = ""

    def add_usage(self, usage: dict[str, int] | None, agent_name: str = "") -> None:
        """Accumulate token usage from an agent result."""
        if not usage:
            return
        for key, val in usage.items():
            if isinstance(val, int | float):
                self.total_usage[key] = self.total_usage.get(key, 0) + int(val)
        if agent_name:
            self.agent_usages.append((agent_name, dict(usage)))

    @property
    def pr_context(self) -> str:
        """Formatted PR context block for agent system prompts (cache-friendly prefix)."""
        parts = []
        if self.pr_body:
            parts.append(f"<pr_description>\n{self.pr_body}\n</pr_description>")
        if self.diff_text:
            parts.append(f"<diff>\n{self.diff_text}\n</diff>")
        return "\n\n".join(parts)

    @property
    def target(self) -> str:
        return f"{self.repo} PR #{self.pr} on {self.handler.platform_name}"

    @property
    def task_started_callback(self) -> Callable[[str, str], None] | None:
        return self.tracker.on_task_started if self.tracker else None

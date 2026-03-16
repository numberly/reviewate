"""Build the sticky status comment body from execution states."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from api.models.executions import Execution

MARKER = "<!-- reviewate-status -->"

# Map workflow DB names to display names
_WORKFLOW_DISPLAY = {
    "review": "review",
    "summarize": "summary",
}


def build_status_body(executions: list[Execution]) -> str:
    """Build status comment body from DB execution states for a PR.

    Groups executions by workflow and maps statuses:
    - queued/processing -> running
    - completed -> completed
    - failed/cancelled -> error

    Args:
        executions: Latest executions per workflow for the PR.

    Returns:
        Full comment body including the HTML marker.
    """
    completed: list[str] = []
    running: list[str] = []
    errors: list[str] = []

    error_details: list[tuple[str, str | None]] = []

    for exc in executions:
        display = _WORKFLOW_DISPLAY.get(exc.workflow, exc.workflow)
        if exc.status in ("queued", "processing"):
            running.append(display)
        elif exc.status == "completed":
            completed.append(display)
        else:
            # failed, cancelled, or any unexpected status
            errors.append(display)
            detail = getattr(exc, "error_detail", None)
            if detail:
                error_details.append((display, detail))

    lines = [MARKER]
    lines.append("#### Reviewate Status Update")
    lines.append(f":white_check_mark: **Completed**: {' & '.join(sorted(completed)) or '0'}")
    if errors:
        lines.append(f"\n:warning:  **Errors**: {' & '.join(sorted(errors))}")
        if error_details:
            for _workflow, detail in error_details:
                if detail is None:
                    continue
                # Truncate long details to keep the comment readable
                truncated = detail if len(detail) <= 200 else detail[:200] + "..."
                lines.append(f"> {truncated}")
        else:
            lines.append("Please check your dashboard for details.")
    if running:
        lines.append(f"\n:runner: **Running**: {' & '.join(sorted(running))}")

    return "\n".join(lines)

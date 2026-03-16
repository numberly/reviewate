"""Structured output for container watcher integration.

Results and errors are printed directly to stdout/stderr to ensure
they're always visible regardless of log level settings.
"""

import json
import sys
import time
from collections import deque
from collections.abc import Callable
from datetime import datetime
from typing import Any

from rich.console import Console, ConsoleOptions, RenderResult
from rich.live import Live
from rich.panel import Panel
from rich.spinner import Spinner
from rich.text import Text

_stderr_console = Console(stderr=True, highlight=False)

# Only show these tool names in the trail
_DISPLAY_TOOLS = {"Read", "Grep", "Glob", "Bash"}

# Maps agent type (from TaskStartedMessage.task_type) to human-readable step labels
_PHASE_LABELS: dict[str, str] = {
    "reviewer": "Running reviewer...",
    "dedup": "Deduplicating reviews...",
    "fact-checker": "Fact-checking reviews...",
    "styler": "Styling reviews...",
}


class _SpinnerWithTrail:
    """Renderable: spinner line + indented tool trail lines below."""

    def __init__(self) -> None:
        self.spinner = Spinner("dots", text="")
        self.trail: list[str] = []

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        # Prepend 2 spaces so spinner char aligns with ✓ at column 2
        frame = self.spinner.render(console.get_time())
        line = Text("  ")
        line.append_text(frame)
        yield line
        for trail_line in self.trail:
            yield Text(f"      {trail_line}", style="dim")


class ProgressTracker:
    """Rich-based CLI progress tracker.

    Prints a branded header, then shows each pipeline step with a spinner
    while active and a checkmark (with detail + duration) once completed.
    Tool calls appear as indented lines below the spinner during execution.
    """

    def __init__(
        self,
        *,
        repo: str,
        pr: str,
        workflows: str,
        model: str,
        console: Console | None = None,
    ) -> None:
        self._console = console or Console(stderr=True, highlight=False)
        self._repo = repo
        self._pr = pr
        self._workflows = workflows
        self._model = model

        self._live: Live | None = None
        self._display: _SpinnerWithTrail | None = None
        self._tool_trail: deque[str] = deque(maxlen=3)
        self._current_step: str | None = None
        self._step_detail: str = ""
        self._step_usage: dict[str, int] | None = None
        self._step_start: float = 0.0
        self._total_start: float = 0.0

    def step(self, msg: str) -> None:
        """Start a new pipeline step."""
        if self._live is None:
            return
        if self._current_step is not None:
            self._print_completed()
        self._current_step = msg
        self._step_detail = ""
        self._step_usage = None
        self._step_start = time.time()
        self._tool_trail.clear()
        if self._display is not None:
            self._display.spinner.update(text=f"[bold cyan]{msg}[/]")
            self._display.trail = []

    def done(self, detail: str, usage: dict[str, int] | None = None) -> None:
        """Attach a result detail and usage to the current step."""
        self._step_detail = detail
        if usage:
            if self._step_usage is None:
                self._step_usage = {}
            for key, val in usage.items():
                if isinstance(val, int | float):
                    self._step_usage[key] = self._step_usage.get(key, 0) + int(val)

    def on_task_started(self, task_type: str, description: str) -> None:
        """Advance the progress step when a subagent task starts.

        Called via TaskStartedMessage from the SDK.
        """
        label = _PHASE_LABELS.get(task_type)
        if label and label != self._current_step:
            self.step(label)

    def on_tool_call(self, agent_name: str, tool_name: str, summary: str = "") -> None:
        """Record a tool call in the trail (shown below the spinner)."""
        if tool_name not in _DISPLAY_TOOLS:
            return
        parts = [p for p in (agent_name, tool_name, summary) if p]
        label = " ".join(parts)
        self._tool_trail.append(label)
        if self._display is not None:
            self._display.trail = list(self._tool_trail)

    def make_tool_callback(self, agent_name: str = "") -> Callable[[str, str, dict], None]:
        """Return a closure suitable for BaseAgent.invoke(on_tool_call=...)."""

        def _callback(tool_name: str, summary: str, input_dict: dict) -> None:
            self.on_tool_call(agent_name, tool_name, summary)

        return _callback

    def start(self) -> None:
        """Print the header panel and start the live display."""
        from code_reviewer import __version__

        self._total_start = time.time()
        body = Text.from_markup(
            f"{self._repo} [bold]#{self._pr}[/] [dim]\u00b7[/] {self._workflows}\n"
            f"[dim]model:[/] {self._model}"
        )
        self._console.print()
        self._console.print(
            Panel(
                body,
                title=f"[bold]Reviewate[/] [dim]v{__version__}[/]",
                title_align="left",
                border_style="cyan",
                expand=False,
                padding=(0, 1),
            )
        )
        self._display = _SpinnerWithTrail()
        self._display.spinner.update(text="[bold cyan]Initializing...[/]")
        self._live = Live(
            self._display, console=self._console, refresh_per_second=12, transient=True
        )
        self._live.start()

    def finish(self, *, cost_usd: float | None = None, usage: dict[str, int] | None = None) -> None:
        """Stop live display, print last completed step, and show total duration."""
        if self._live is None:
            return
        self._live.stop()
        self._print_completed()
        elapsed = time.time() - self._total_start
        self._console.print(f"\n  [bold green]\u2713 Done in {elapsed:.1f}s[/]")
        if usage:
            self._console.print(f"  [dim]{_format_usage(usage)}[/]")
        self._console.print()
        self._live = None
        self._display = None

    def fail(self, error: str) -> None:
        """Stop live display and show current step as failed."""
        if self._live is None:
            return
        self._live.stop()
        self._console.print(f"  [red]\u2717[/] {self._current_step}")
        self._console.print(f"\n  [bold red]Error: {error}[/]")
        self._console.print()
        self._live = None
        self._display = None

    def print_lgtm(self) -> None:
        """Print a 'looks good' message when the review found no issues."""
        self._console.print("  [green]No issues found — LGTM![/]")
        self._console.print()

    def print_review_panels(self, comments: list) -> None:
        """Print one Rich panel per review comment."""
        for comment in comments:
            path = getattr(comment, "path", None) or getattr(comment, "new_path", "?")
            line = getattr(comment, "line", None) or getattr(comment, "new_line", "?")
            body = getattr(comment, "body", str(comment))
            self._console.print(
                Panel(
                    body,
                    title=f"[bold]{path}:{line}[/]",
                    title_align="left",
                    border_style="cyan",
                    expand=False,
                    padding=(0, 1),
                )
            )

    def print_summary_panel(self, summary_text: str) -> None:
        """Print a single Rich panel with the summary."""
        self._console.print(
            Panel(
                summary_text,
                title="[bold]Summary[/]",
                title_align="left",
                border_style="cyan",
                expand=False,
                padding=(0, 1),
            )
        )

    def _print_completed(self) -> None:
        if self._current_step is not None:
            elapsed = time.time() - self._step_start
            detail = f" [dim]{self._step_detail}[/]" if self._step_detail else ""
            usage_str = ""
            if self._step_usage:
                usage_str = f" [dim]{_format_usage(self._step_usage)}[/]"
            self._console.print(
                f"  [green]\u2713[/] {self._current_step}{detail}"
                f" [dim]({elapsed:.1f}s)[/]{usage_str}"
            )


def _format_usage(usage: dict[str, int]) -> str:
    """Format usage dict into a compact readable string."""
    in_t = usage.get("input_tokens", 0)
    out_t = usage.get("output_tokens", 0)
    cache_r = usage.get("cache_read_input_tokens", 0)
    cache_w = usage.get("cache_creation_input_tokens", 0)
    parts = [f"{in_t:,} in", f"{out_t:,} out"]
    if cache_r:
        parts.append(f"{cache_r:,} cache read")
    if cache_w:
        parts.append(f"{cache_w:,} cache write")
    return " · ".join(parts)


def _timestamp() -> str:
    """Get current timestamp in log format."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def emit_result(
    data: dict[str, Any], include_reviews: bool = False, *, is_tty: bool = False
) -> None:
    """Emit structured result for container watcher.

    Format: [TIMESTAMP] [INFO] [output.output] output=output [REVIEWATE:RESULT] {...json...}

    Suppressed in TTY mode since humans see the ProgressTracker output instead.
    """
    if is_tty:
        return
    if not include_reviews:
        data = {k: v for k, v in data.items() if k not in ("review_output",)}
    print(
        f"[{_timestamp()}] [INFO    ] [output.output] output=output [REVIEWATE:RESULT] {json.dumps(data)}",
        file=sys.stdout,
    )


def emit_error(
    error_type: str, message: str, details: dict[str, Any] | None = None, *, is_tty: bool = False
) -> None:
    """Emit structured error for container watcher.

    Format: [TIMESTAMP] [ERROR] [output.output] output=output [REVIEWATE:ERROR] {...json...}

    Suppressed in TTY mode — callers use print_error() or ProgressTracker.fail() instead.
    """
    if is_tty:
        return
    error_data: dict[str, Any] = {"type": error_type, "message": message}
    if details:
        error_data.update(details)
    print(
        f"[{_timestamp()}] [ERROR   ] [output.output] output=output [REVIEWATE:ERROR] {json.dumps(error_data)}",
        file=sys.stderr,
    )


def print_error(message: str, *, hint: str | None = None) -> None:
    """Print a rich-formatted error panel to stderr (for TTY mode)."""
    body = Text(message)
    if hint:
        body.append(f"\n{hint}", style="dim")
    _stderr_console.print()
    _stderr_console.print(
        Panel(body, title="[red]Error[/]", border_style="red", expand=False, padding=(0, 1))
    )
    _stderr_console.print()

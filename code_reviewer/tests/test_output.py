"""Tests for structured output emission."""

import json
from io import StringIO
from unittest.mock import MagicMock

from rich.console import Console

from code_reviewer.output import ProgressTracker, emit_error, emit_result, print_error


class TestEmitResult:
    def test_emits_json_to_stdout(self, capsys):
        data = {"status": "success", "workflows": [{"name": "review"}]}
        emit_result(data)
        captured = capsys.readouterr()
        assert "[REVIEWATE:RESULT]" in captured.out
        parsed = json.loads(captured.out.split("[REVIEWATE:RESULT] ")[1])
        assert parsed["status"] == "success"

    def test_strips_review_output_by_default(self, capsys):
        data = {"status": "success", "review_output": "long text"}
        emit_result(data, include_reviews=False)
        captured = capsys.readouterr()
        parsed = json.loads(captured.out.split("[REVIEWATE:RESULT] ")[1])
        assert "review_output" not in parsed

    def test_includes_reviews_when_requested(self, capsys):
        data = {"status": "success", "review_output": "long text"}
        emit_result(data, include_reviews=True)
        captured = capsys.readouterr()
        parsed = json.loads(captured.out.split("[REVIEWATE:RESULT] ")[1])
        assert parsed["review_output"] == "long text"

    def test_suppressed_in_tty_mode(self, capsys):
        data = {"status": "success"}
        emit_result(data, is_tty=True)
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_emits_when_not_tty(self, capsys):
        data = {"status": "success"}
        emit_result(data, is_tty=False)
        captured = capsys.readouterr()
        assert "[REVIEWATE:RESULT]" in captured.out


class TestEmitError:
    def test_emits_json_to_stderr(self, capsys):
        emit_error("internal_error", "something broke")
        captured = capsys.readouterr()
        assert "[REVIEWATE:ERROR]" in captured.err
        parsed = json.loads(captured.err.split("[REVIEWATE:ERROR] ")[1])
        assert parsed["type"] == "internal_error"
        assert parsed["message"] == "something broke"

    def test_includes_details(self, capsys):
        emit_error("timeout", "timed out", details={"duration": 600})
        captured = capsys.readouterr()
        parsed = json.loads(captured.err.split("[REVIEWATE:ERROR] ")[1])
        assert parsed["duration"] == 600

    def test_suppressed_in_tty_mode(self, capsys):
        emit_error("internal_error", "something broke", is_tty=True)
        captured = capsys.readouterr()
        assert captured.err == ""

    def test_emits_when_not_tty(self, capsys):
        emit_error("internal_error", "something broke", is_tty=False)
        captured = capsys.readouterr()
        assert "[REVIEWATE:ERROR]" in captured.err


class TestPrintError:
    def test_prints_to_stderr(self, capsys):
        print_error("something broke")
        captured = capsys.readouterr()
        assert "something broke" in captured.err

    def test_prints_hint(self, capsys):
        print_error("auth failed", hint="Set ANTHROPIC_API_KEY")
        captured = capsys.readouterr()
        assert "auth failed" in captured.err
        assert "Set ANTHROPIC_API_KEY" in captured.err


class TestProgressTrackerPhases:
    """Tests for on_task_started phase detection logic."""

    def _make_tracker(self):
        tracker = ProgressTracker(repo="o/r", pr="1", workflows="review", model="sonnet")
        tracker.step = MagicMock()
        return tracker

    def test_reviewer_advances_step(self):
        tracker = self._make_tracker()
        tracker.on_task_started("reviewer", "Code review analyzer")
        tracker.step.assert_called_with("Running reviewer...")

    def test_dedup_advances_step(self):
        tracker = self._make_tracker()
        tracker.on_task_started("dedup", "Deduplication agent")
        tracker.step.assert_called_with("Deduplicating reviews...")

    def test_fact_checker_advances_step(self):
        tracker = self._make_tracker()
        tracker.on_task_started("fact-checker", "Fact checker")
        tracker.step.assert_called_with("Fact-checking reviews...")

    def test_styler_advances_step(self):
        tracker = self._make_tracker()
        tracker.on_task_started("styler", "Formatter")
        tracker.step.assert_called_with("Styling reviews...")

    def test_unknown_task_type_ignored(self):
        tracker = self._make_tracker()
        tracker.on_task_started("unknown-agent", "Some agent")
        tracker.step.assert_not_called()

    def test_duplicate_step_skipped(self):
        """Second reviewer task (parallel) should not re-emit the same step."""
        tracker = self._make_tracker()
        tracker._current_step = "Running reviewer..."
        tracker.on_task_started("reviewer", "Code review analyzer")
        tracker.step.assert_not_called()


class TestToolTrail:
    """Tests for tool trail tracking below the spinner."""

    def _make_tracker(self):
        tracker = ProgressTracker(repo="o/r", pr="1", workflows="review", model="sonnet")
        # Don't actually start Live — just set up internal state
        tracker._display = MagicMock()
        tracker._display.trail = []
        tracker._live = MagicMock()
        tracker._current_step = "Running reviewers..."
        return tracker

    def test_display_tools_shown(self):
        tracker = self._make_tracker()
        tracker.on_tool_call("", "Read", "src/main.py")
        assert list(tracker._tool_trail) == ["Read src/main.py"]

    def test_non_display_tools_filtered(self):
        tracker = self._make_tracker()
        tracker.on_tool_call("", "ToolSearch", "query")
        tracker.on_tool_call("", "Write", "file.py")
        assert list(tracker._tool_trail) == []

    def test_agent_name_prefix(self):
        tracker = self._make_tracker()
        tracker.on_tool_call("Analyzer[0]", "Read", "src/main.py")
        assert list(tracker._tool_trail) == ["Analyzer[0] Read src/main.py"]

    def test_no_agent_name(self):
        tracker = self._make_tracker()
        tracker.on_tool_call("", "Grep", "TODO in src/")
        assert list(tracker._tool_trail) == ["Grep TODO in src/"]

    def test_no_summary(self):
        tracker = self._make_tracker()
        tracker.on_tool_call("", "Read")
        assert list(tracker._tool_trail) == ["Read"]

    def test_maxlen_3(self):
        tracker = self._make_tracker()
        tracker.on_tool_call("", "Read", "a.py")
        tracker.on_tool_call("", "Grep", "b")
        tracker.on_tool_call("", "Glob", "*.py")
        tracker.on_tool_call("", "Bash", "git status")
        assert list(tracker._tool_trail) == ["Grep b", "Glob *.py", "Bash git status"]

    def test_display_trail_synced(self):
        tracker = self._make_tracker()
        tracker.on_tool_call("A", "Read", "f.py")
        tracker.on_tool_call("B", "Grep", "err in src/")
        tracker._display.trail = list(tracker._tool_trail)
        assert tracker._display.trail == ["A Read f.py", "B Grep err in src/"]

    def test_step_clears_trail(self):
        tracker = self._make_tracker()
        tracker.on_tool_call("", "Read")
        tracker.on_tool_call("", "Grep")
        assert len(tracker._tool_trail) == 2
        tracker.step("Fact-checking...")
        assert list(tracker._tool_trail) == []


class TestMakeToolCallback:
    """Tests for make_tool_callback closure."""

    def test_callback_calls_on_tool_call(self):
        tracker = ProgressTracker(repo="o/r", pr="1", workflows="review", model="sonnet")
        tracker.on_tool_call = MagicMock()
        cb = tracker.make_tool_callback("Analyzer[0]")
        cb("Read", "src/main.py", {"file_path": "src/main.py"})
        tracker.on_tool_call.assert_called_once_with("Analyzer[0]", "Read", "src/main.py")

    def test_callback_without_agent_name(self):
        tracker = ProgressTracker(repo="o/r", pr="1", workflows="review", model="sonnet")
        tracker.on_tool_call = MagicMock()
        cb = tracker.make_tool_callback()
        cb("Bash", "git status", {"command": "git status"})
        tracker.on_tool_call.assert_called_once_with("", "Bash", "git status")


class TestResultPanels:
    """Tests for review and summary panel output."""

    def _make_tracker_with_buffer(self):
        buf = StringIO()
        console = Console(file=buf, force_terminal=True, width=80)
        tracker = ProgressTracker(
            repo="o/r", pr="1", workflows="review", model="sonnet", console=console
        )
        return tracker, buf

    def test_review_panels_one_per_comment(self):
        tracker, buf = self._make_tracker_with_buffer()
        comments = [
            MagicMock(path="src/main.py", line=42, body="Bug: missing null check"),
            MagicMock(path="src/utils.ts", line=15, body="Suggestion: use const"),
        ]
        tracker.print_review_panels(comments)
        output = buf.getvalue()
        assert "src/main.py:42" in output
        assert "Bug: missing null check" in output
        assert "src/utils.ts:15" in output
        assert "Suggestion: use const" in output

    def test_review_panels_gitlab_fields(self):
        tracker, buf = self._make_tracker_with_buffer()
        comment = MagicMock(spec=["new_path", "new_line", "body"])
        comment.new_path = "lib/api.rb"
        comment.new_line = 99
        comment.body = "Consider extracting method"
        tracker.print_review_panels([comment])
        output = buf.getvalue()
        assert "lib/api.rb:99" in output
        assert "Consider extracting method" in output

    def test_summary_panel(self):
        tracker, buf = self._make_tracker_with_buffer()
        tracker.print_summary_panel("This PR adds input validation.")
        output = buf.getvalue()
        assert "Summary" in output
        assert "This PR adds input validation." in output

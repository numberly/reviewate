"""Tests for status_comment module."""

from api.plugins.container.status_comment import MARKER, build_status_body
from tests.utils.factories import ExecutionFactory


def test_single_running_execution():
    """Single queued execution shows Running: review."""
    executions = [ExecutionFactory.build(workflow="review", status="queued")]
    body = build_status_body(executions)

    assert MARKER in body
    assert "Completed**: 0" in body
    assert "Running**: review" in body
    assert "Errors" not in body


def test_single_completed_execution():
    """Single completed execution shows Completed: review."""
    executions = [ExecutionFactory.build(workflow="review", status="completed")]
    body = build_status_body(executions)

    assert "Completed**: review" in body
    assert "Running" not in body
    assert "Errors" not in body


def test_both_workflows_running():
    """Two running workflows show both in Running."""
    executions = [
        ExecutionFactory.build(workflow="review", status="processing"),
        ExecutionFactory.build(workflow="summarize", status="queued"),
    ]
    body = build_status_body(executions)

    assert "Completed**: 0" in body
    assert "review" in body
    assert "summary" in body


def test_one_completed_one_running():
    """One completed, one running."""
    executions = [
        ExecutionFactory.build(workflow="review", status="processing"),
        ExecutionFactory.build(workflow="summarize", status="completed"),
    ]
    body = build_status_body(executions)

    assert "Completed**: summary" in body
    assert "Running**: review" in body


def test_both_completed():
    """Both workflows completed."""
    executions = [
        ExecutionFactory.build(workflow="review", status="completed"),
        ExecutionFactory.build(workflow="summarize", status="completed"),
    ]
    body = build_status_body(executions)

    assert "Completed**: review & summary" in body
    assert "Running" not in body


def test_failed_execution_shows_in_errors():
    """Failed execution shows in Errors section."""
    executions = [
        ExecutionFactory.build(workflow="review", status="failed"),
        ExecutionFactory.build(workflow="summarize", status="processing"),
    ]
    body = build_status_body(executions)

    assert "Completed**: 0" in body
    assert "Errors**: review" in body
    assert "Running**: summary" in body


def test_cancelled_counts_as_error():
    """Cancelled execution shows in Errors section."""
    executions = [ExecutionFactory.build(workflow="review", status="cancelled")]
    body = build_status_body(executions)

    assert "Errors**: review" in body


def test_empty_executions():
    """Empty list produces all-zero body."""
    body = build_status_body([])

    assert MARKER in body
    assert "Completed**: 0" in body
    assert "Running" not in body


def test_marker_is_first_line():
    """Marker should be the first line."""
    executions = [ExecutionFactory.build(workflow="review", status="queued")]
    body = build_status_body(executions)

    assert body.split("\n")[0] == MARKER


def test_failed_execution_shows_error_detail():
    """Failed execution with error_detail includes the detail in the comment."""
    executions = [
        ExecutionFactory.build(
            workflow="review",
            status="failed",
            error_detail="Branch 'feature/xyz' not found in owner/repo — it may have been deleted",
        ),
    ]
    body = build_status_body(executions)

    assert "Errors**: review" in body
    assert "Branch 'feature/xyz' not found" in body
    assert "it may have been deleted" in body


def test_failed_execution_without_error_detail_shows_fallback():
    """Failed execution without error_detail shows generic fallback message."""
    executions = [
        ExecutionFactory.build(workflow="review", status="failed", error_detail=None),
    ]
    body = build_status_body(executions)

    assert "Errors**: review" in body
    assert "Please check your dashboard for details." in body


def test_failed_execution_truncates_long_error_detail():
    """Long error details are truncated to 200 chars."""
    long_detail = "x" * 300
    executions = [
        ExecutionFactory.build(workflow="review", status="failed", error_detail=long_detail),
    ]
    body = build_status_body(executions)

    assert "Errors**: review" in body
    assert "x" * 200 + "..." in body
    assert "x" * 201 not in body

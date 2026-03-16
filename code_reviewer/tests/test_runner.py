"""Tests for the runner module with mocked agents."""

import argparse
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from code_reviewer.adaptors.repository.github.schema import GitHubReviewComment
from code_reviewer.adaptors.repository.handler import RepositoryHandler
from code_reviewer.adaptors.repository.schema import Review
from code_reviewer.runner import run
from code_reviewer.workflows.review.schema import ReviewResult


def _make_mock_handler():
    """Create a mock RepositoryHandler."""
    handler = MagicMock(spec=RepositoryHandler)
    handler.platform_name = "github"
    handler.validate_pr.return_value = "PR title"
    handler.download_source.return_value = None
    handler.fetch_pr_body.return_value = ""
    handler.fetch_diff.return_value = ""
    return handler


_MOCK_HANDLER = _make_mock_handler()


def _patch_handler(handler=None):
    """Patch get_handler to return a mock handler."""
    h = handler or _make_mock_handler()
    return patch("code_reviewer.runner.get_handler", return_value=h)


def _make_args(**overrides):
    """Create a mock args namespace."""
    defaults = {
        "repo": "owner/repo",
        "pr": "123",
        "platform": "github",
        "dry_run": False,
        "debug": False,
        "json": False,
        "model": None,
        "review": True,
        "summary": False,
        "command": "review",
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _make_review_result(comments=None, cost=None):
    """Create a ReviewResult for mocking."""
    review = Review[GitHubReviewComment](comments=comments or [])
    return ReviewResult(review=review, cost_usd=cost)


def _patch_pipeline(result=None):
    """Patch _run_pipeline to return a mock ReviewResult."""
    r = result or _make_review_result()
    return patch("code_reviewer.workflows.review.runner._run_pipeline", AsyncMock(return_value=r))


class TestRunner:
    @pytest.mark.asyncio
    async def test_run_fails_without_credentials(self):
        args = _make_args()
        env = {"ANTHROPIC_API_KEY": "", "CLAUDE_CODE_OAUTH_TOKEN": ""}
        with patch.dict("os.environ", env, clear=True):
            result = await run(args)
        assert result == 1

    @pytest.mark.asyncio
    async def test_run_review_success(self):
        args = _make_args()

        env = {"ANTHROPIC_API_KEY": "sk-test"}
        with (
            patch.dict("os.environ", env, clear=True),
            _patch_pipeline() as mock_pipeline,
            _patch_handler(),
        ):
            result = await run(args)

        assert result == 0
        mock_pipeline.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_run_summary_success(self):
        args = _make_args(review=False, summary=True, command="summary")

        env = {"ANTHROPIC_API_KEY": "sk-test"}
        with (
            patch.dict("os.environ", env, clear=True),
            patch("code_reviewer.runner.run_summary", new_callable=AsyncMock) as mock_summary,
            _patch_handler(),
        ):
            result = await run(args)

        assert result == 0
        mock_summary.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_run_full_both_workflows(self):
        args = _make_args(review=True, summary=True, command="full")

        env = {"ANTHROPIC_API_KEY": "sk-test"}
        with (
            patch.dict("os.environ", env, clear=True),
            _patch_pipeline() as mock_pipeline,
            patch("code_reviewer.runner.run_summary", new_callable=AsyncMock) as mock_summary,
            _patch_handler(),
        ):
            result = await run(args)

        assert result == 0
        mock_pipeline.assert_awaited_once()
        mock_summary.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_run_handles_exception(self):
        args = _make_args(debug=False)

        env = {"ANTHROPIC_API_KEY": "sk-test"}
        with (
            patch.dict("os.environ", env, clear=True),
            patch(
                "code_reviewer.workflows.review.runner._run_pipeline",
                AsyncMock(side_effect=RuntimeError("boom")),
            ),
            _patch_handler(),
        ):
            result = await run(args)

        assert result == 1

    @pytest.mark.asyncio
    async def test_run_dry_run_skips_guardrail_and_posting(self):
        """In dry-run mode, comments are returned but not guardrailed or posted."""
        comments = [GitHubReviewComment(path="a.py", line=1, body="**Bug: T**\n\nB")]
        args = _make_args(dry_run=True)

        handler = _make_mock_handler()
        env = {"ANTHROPIC_API_KEY": "sk-test"}
        with (
            patch.dict("os.environ", env, clear=True),
            _patch_pipeline(_make_review_result(comments=comments)),
            patch("code_reviewer.workflows.review.utils.guardrail_check") as mock_guardrail,
            _patch_handler(handler),
        ):
            result = await run(args)

        assert result == 0
        mock_guardrail.assert_not_called()
        handler.post_review.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_debug_mode_skips_tracker(self):
        """In debug+TTY mode, no ProgressTracker is created."""
        args = _make_args(debug=True)

        env = {"ANTHROPIC_API_KEY": "sk-test"}
        with (
            patch.dict("os.environ", env, clear=True),
            _patch_pipeline(),
            patch("code_reviewer.runner.sys") as mock_sys,
            _patch_handler(),
        ):
            mock_sys.stderr.isatty.return_value = True
            result = await run(args)

        assert result == 0

    @pytest.mark.asyncio
    async def test_validate_failure_returns_error(self):
        """If PR validation fails, runner returns 1 without starting agents."""
        args = _make_args()

        handler = _make_mock_handler()
        handler.validate_pr.side_effect = RuntimeError("PR not found")
        env = {"ANTHROPIC_API_KEY": "sk-test"}
        with (
            patch.dict("os.environ", env, clear=True),
            _patch_handler(handler),
        ):
            result = await run(args)

        assert result == 1

    @pytest.mark.asyncio
    async def test_download_failure_returns_error(self):
        """If source download fails, runner returns 1 without starting agents."""
        args = _make_args()

        handler = _make_mock_handler()
        handler.download_source.side_effect = RuntimeError("Download failed")
        env = {"ANTHROPIC_API_KEY": "sk-test"}
        with (
            patch.dict("os.environ", env, clear=True),
            _patch_handler(handler),
        ):
            result = await run(args)

        assert result == 1

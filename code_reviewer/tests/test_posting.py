"""Tests for repository handlers and posting types."""

import json
from unittest.mock import patch

from code_reviewer.adaptors.repository.github.handler import GitHubHandler
from code_reviewer.adaptors.repository.github.schema import GitHubReviewComment
from code_reviewer.adaptors.repository.gitlab.handler import GitLabHandler
from code_reviewer.adaptors.repository.gitlab.schema import GitLabReviewComment
from code_reviewer.adaptors.repository.schema import PostFailure, PostResult, Review


def _make_github_comment(**overrides):
    defaults = {"path": "src/main.py", "line": 42, "body": "**Bug: T**\n\nB"}
    defaults.update(overrides)
    return GitHubReviewComment(**defaults)


def _make_gitlab_comment(**overrides):
    defaults = {"new_path": "src/main.py", "new_line": 42, "body": "**Bug: T**\n\nB"}
    defaults.update(overrides)
    return GitLabReviewComment(**defaults)


def _mock_subprocess_ok(stdout="", stderr=""):
    """Create a mock CompletedProcess with returncode 0."""
    from subprocess import CompletedProcess

    return CompletedProcess(args=[], returncode=0, stdout=stdout, stderr=stderr)


def _mock_subprocess_fail(stderr="error"):
    """Create a mock CompletedProcess with returncode 1."""
    from subprocess import CompletedProcess

    return CompletedProcess(args=[], returncode=1, stdout="", stderr=stderr)


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


class TestGitHubReviewComment:
    def test_defaults(self):
        comment = GitHubReviewComment(path="a.py", line=10, body="text")
        assert comment.side is None

    def test_left_side(self):
        comment = GitHubReviewComment(path="a.py", line=10, body="text", side="LEFT")
        assert comment.side == "LEFT"

    def test_serialization(self):
        comment = GitHubReviewComment(path="a.py", line=10, body="text", side="RIGHT")
        data = comment.model_dump()
        assert data["side"] == "RIGHT"
        assert data["path"] == "a.py"


class TestGitLabReviewComment:
    def test_defaults(self):
        comment = GitLabReviewComment(new_path="a.py", new_line=10, body="text")
        assert comment.old_path is None
        assert comment.old_line is None

    def test_old_fields(self):
        comment = GitLabReviewComment(body="text", old_path="old.py", old_line=5)
        assert comment.old_path == "old.py"
        assert comment.old_line == 5


class TestReviewGeneric:
    def test_github_review_schema(self):
        schema = Review[GitHubReviewComment].model_json_schema()
        assert "comments" in schema["properties"]

    def test_gitlab_review_schema(self):
        schema = Review[GitLabReviewComment].model_json_schema()
        assert "comments" in schema["properties"]

    def test_github_review_roundtrip(self):
        review = Review[GitHubReviewComment](
            comments=[GitHubReviewComment(path="a.py", line=10, body="text", side="RIGHT")]
        )
        data = json.loads(review.model_dump_json())
        assert data["comments"][0]["side"] == "RIGHT"

    def test_gitlab_review_roundtrip(self):
        review = Review[GitLabReviewComment](
            comments=[GitLabReviewComment(body="text", new_path="a.py", new_line=10)]
        )
        data = json.loads(review.model_dump_json())
        assert data["comments"][0]["new_path"] == "a.py"


# ---------------------------------------------------------------------------
# GitHub handler tests
# ---------------------------------------------------------------------------


class TestPostReviewEmpty:
    def test_empty_returns_empty_result(self):
        handler = GitHubHandler()
        review = Review[GitHubReviewComment](comments=[])
        result = handler.post_review(review, "o/r", "1", {})
        assert result.posted == 0
        assert result.failed == []


class TestGitHubHandler:
    @patch("code_reviewer.adaptors.repository.github.handler.subprocess.run")
    def test_posts_inline_comments(self, mock_run):
        mock_run.return_value = _mock_subprocess_ok()
        handler = GitHubHandler()
        review = Review[GitHubReviewComment](
            comments=[_make_github_comment(), _make_github_comment(path="b.py", line=10)]
        )
        result = handler.post_review(review, "o/r", "1", {})
        assert result.posted == 2
        assert result.failed == []
        assert mock_run.call_count == 1
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "gh"
        assert "repos/o/r/pulls/1/reviews" in cmd

    @patch("code_reviewer.adaptors.repository.github.handler.subprocess.run")
    def test_body_passed_through(self, mock_run):
        """Body is passed as-is (agent already formatted it)."""
        mock_run.return_value = _mock_subprocess_ok()
        handler = GitHubHandler()
        review = Review[GitHubReviewComment](
            comments=[_make_github_comment(body="**Critical: XSS**\n\nDetails")]
        )
        handler.post_review(review, "o/r", "1", {})
        input_path = mock_run.call_args[0][0][-1]
        with open(input_path) as f:
            payload = json.load(f)
        assert payload["comments"][0]["body"] == "**Critical: XSS**\n\nDetails"

    @patch("code_reviewer.adaptors.repository.github.handler.subprocess.run")
    def test_side_passed_through(self, mock_run):
        """Side field is included in GitHub payload."""
        mock_run.return_value = _mock_subprocess_ok()
        handler = GitHubHandler()
        review = Review[GitHubReviewComment](comments=[_make_github_comment(side="LEFT")])
        handler.post_review(review, "o/r", "1", {})
        input_path = mock_run.call_args[0][0][-1]
        with open(input_path) as f:
            payload = json.load(f)
        assert payload["comments"][0]["side"] == "LEFT"

    @patch("code_reviewer.adaptors.repository.github.handler.subprocess.run")
    def test_fallback_comment_for_no_line(self, mock_run):
        mock_run.return_value = _mock_subprocess_ok()
        handler = GitHubHandler()
        review = Review[GitHubReviewComment](comments=[_make_github_comment(line=None)])
        result = handler.post_review(review, "o/r", "1", {})
        assert result.posted == 1
        cmd = mock_run.call_args[0][0]
        assert "pr" in cmd
        assert "comment" in cmd

    @patch("code_reviewer.adaptors.repository.github.handler.subprocess.run")
    def test_failed_review_records_failures(self, mock_run):
        mock_run.return_value = _mock_subprocess_fail("422 Unprocessable Entity")
        handler = GitHubHandler()
        review = Review[GitHubReviewComment](comments=[_make_github_comment()])
        result = handler.post_review(review, "o/r", "1", {})
        assert result.posted == 0
        assert len(result.failed) == 1
        assert "422" in result.failed[0].error

    @patch("code_reviewer.adaptors.repository.github.handler.subprocess.run")
    def test_batch_failure_falls_back_to_individual(self, mock_run):
        mock_run.side_effect = [
            _mock_subprocess_fail("422 Unprocessable Entity"),
            _mock_subprocess_ok(),
            _mock_subprocess_ok(),
        ]
        handler = GitHubHandler()
        review = Review[GitHubReviewComment](
            comments=[_make_github_comment(), _make_github_comment(path="b.py", line=10)]
        )
        result = handler.post_review(review, "o/r", "1", {})
        assert result.posted == 2
        assert result.failed == []
        assert mock_run.call_count == 3

    @patch("code_reviewer.adaptors.repository.github.handler.subprocess.run")
    def test_batch_failure_partial_individual_success(self, mock_run):
        mock_run.side_effect = [
            _mock_subprocess_fail("422 Unprocessable Entity"),
            _mock_subprocess_ok(),
            _mock_subprocess_fail("line not in diff"),
        ]
        handler = GitHubHandler()
        review = Review[GitHubReviewComment](
            comments=[_make_github_comment(), _make_github_comment(path="b.py", line=999)]
        )
        result = handler.post_review(review, "o/r", "1", {})
        assert result.posted == 1
        assert len(result.failed) == 1

    @patch("code_reviewer.adaptors.repository.github.handler.subprocess.run")
    def test_mixed_inline_and_fallback(self, mock_run):
        mock_run.return_value = _mock_subprocess_ok()
        handler = GitHubHandler()
        review = Review[GitHubReviewComment](
            comments=[_make_github_comment(), _make_github_comment(line=None)]
        )
        result = handler.post_review(review, "o/r", "1", {})
        assert result.posted == 2
        assert mock_run.call_count == 2


# ---------------------------------------------------------------------------
# GitLab handler tests
# ---------------------------------------------------------------------------


class TestGitLabHandler:
    @patch("code_reviewer.adaptors.repository.gitlab.handler.subprocess.run")
    def test_posts_inline_notes(self, mock_run):
        versions_response = json.dumps(
            [
                {
                    "base_commit_sha": "aaa",
                    "head_commit_sha": "bbb",
                    "start_commit_sha": "ccc",
                }
            ]
        )
        mock_run.return_value = _mock_subprocess_ok(stdout=versions_response)
        handler = GitLabHandler()
        review = Review[GitLabReviewComment](comments=[_make_gitlab_comment()])
        result = handler.post_review(review, "group/proj", "1", {})
        assert mock_run.call_count == 2
        assert result.posted == 1

    @patch("code_reviewer.adaptors.repository.gitlab.handler.subprocess.run")
    def test_inline_uses_typed_payload(self, mock_run):
        versions_response = json.dumps(
            [
                {
                    "base_commit_sha": "aaa",
                    "head_commit_sha": "bbb",
                    "start_commit_sha": "ccc",
                }
            ]
        )
        mock_run.return_value = _mock_subprocess_ok(stdout=versions_response)
        handler = GitLabHandler()
        review = Review[GitLabReviewComment](
            comments=[_make_gitlab_comment(body="**Security: Hardcoded secret**\n\nDetails")]
        )
        handler.post_review(review, "group/proj", "1", {})
        note_call = mock_run.call_args_list[1]
        input_path = note_call[0][0][-3]
        with open(input_path) as f:
            payload = json.load(f)
        assert payload["position"]["position_type"] == "text"
        assert payload["position"]["base_sha"] == "aaa"
        assert payload["position"]["new_line"] == 42
        assert payload["body"] == "**Security: Hardcoded secret**\n\nDetails"

    @patch("code_reviewer.adaptors.repository.gitlab.handler.subprocess.run")
    def test_old_line_used_when_set(self, mock_run):
        """GitLab comments with old_line include it in position."""
        versions_response = json.dumps(
            [
                {
                    "base_commit_sha": "aaa",
                    "head_commit_sha": "bbb",
                    "start_commit_sha": "ccc",
                }
            ]
        )
        mock_run.return_value = _mock_subprocess_ok(stdout=versions_response)
        handler = GitLabHandler()
        review = Review[GitLabReviewComment](
            comments=[GitLabReviewComment(body="text", old_path="old.py", old_line=10)]
        )
        handler.post_review(review, "group/proj", "1", {})
        note_call = mock_run.call_args_list[1]
        input_path = note_call[0][0][-3]
        with open(input_path) as f:
            payload = json.load(f)
        assert payload["position"]["old_line"] == 10
        assert "new_line" not in payload["position"]

    @patch("code_reviewer.adaptors.repository.gitlab.handler.subprocess.run")
    def test_old_path_used_when_set(self, mock_run):
        """GitLab comments with old_path use it in the position."""
        versions_response = json.dumps(
            [
                {
                    "base_commit_sha": "aaa",
                    "head_commit_sha": "bbb",
                    "start_commit_sha": "ccc",
                }
            ]
        )
        mock_run.return_value = _mock_subprocess_ok(stdout=versions_response)
        handler = GitLabHandler()
        review = Review[GitLabReviewComment](
            comments=[_make_gitlab_comment(old_path="old_main.py")]
        )
        handler.post_review(review, "group/proj", "1", {})
        note_call = mock_run.call_args_list[1]
        input_path = note_call[0][0][-3]
        with open(input_path) as f:
            payload = json.load(f)
        assert payload["position"]["old_path"] == "old_main.py"
        assert payload["position"]["new_path"] == "src/main.py"

    @patch("code_reviewer.adaptors.repository.gitlab.handler.subprocess.run")
    def test_versions_failure_marks_all_failed(self, mock_run):
        mock_run.return_value = _mock_subprocess_fail("403 Forbidden")
        handler = GitLabHandler()
        review = Review[GitLabReviewComment](
            comments=[_make_gitlab_comment(), _make_gitlab_comment(new_path="b.py")]
        )
        result = handler.post_review(review, "group/proj", "1", {})
        assert result.posted == 0
        assert len(result.failed) == 2

    @patch("code_reviewer.adaptors.repository.gitlab.handler.subprocess.run")
    def test_fallback_note_for_no_line(self, mock_run):
        versions_response = json.dumps(
            [
                {
                    "base_commit_sha": "aaa",
                    "head_commit_sha": "bbb",
                    "start_commit_sha": "ccc",
                }
            ]
        )
        mock_run.return_value = _mock_subprocess_ok(stdout=versions_response)
        handler = GitLabHandler()
        review = Review[GitLabReviewComment](comments=[GitLabReviewComment(body="general comment")])
        result = handler.post_review(review, "group/proj", "1", {})
        assert mock_run.call_count == 2
        assert result.posted == 1


# ---------------------------------------------------------------------------
# post_regular_comment fallback tests
# ---------------------------------------------------------------------------


class TestPostRegularComment:
    @patch("code_reviewer.adaptors.repository.github.handler.subprocess.run")
    def test_github_comment(self, mock_run):
        mock_run.return_value = _mock_subprocess_ok()
        handler = GitHubHandler()
        assert handler.post_regular_comment(_make_github_comment(), "o/r", "1", {}) is True
        cmd = mock_run.call_args[0][0]
        assert cmd[:3] == ["gh", "pr", "comment"]

    @patch("code_reviewer.adaptors.repository.gitlab.handler.subprocess.run")
    def test_gitlab_comment(self, mock_run):
        mock_run.return_value = _mock_subprocess_ok()
        handler = GitLabHandler()
        assert handler.post_regular_comment(_make_gitlab_comment(), "g/p", "1", {}) is True
        cmd = mock_run.call_args[0][0]
        assert cmd[:3] == ["glab", "mr", "note"]

    @patch("code_reviewer.adaptors.repository.github.handler.subprocess.run")
    def test_returns_false_on_failure(self, mock_run):
        mock_run.return_value = _mock_subprocess_fail("error")
        handler = GitHubHandler()
        assert handler.post_regular_comment(_make_github_comment(), "o/r", "1", {}) is False


# ---------------------------------------------------------------------------
# PostResult tests
# ---------------------------------------------------------------------------


class TestPostResult:
    def test_all_posted_true(self):
        result = PostResult(posted=3)
        assert result.all_posted is True

    def test_all_posted_false_with_failures(self):
        result = PostResult(
            posted=1, failed=[PostFailure(comment=_make_github_comment(), error="err")]
        )
        assert result.all_posted is False

    def test_all_posted_false_when_empty(self):
        result = PostResult()
        assert result.all_posted is False

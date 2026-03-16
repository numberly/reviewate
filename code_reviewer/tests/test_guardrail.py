"""Tests for the gitleaks-based guardrail."""

import json
import shutil
from subprocess import CompletedProcess
from unittest.mock import patch

import pytest

from code_reviewer.adaptors.repository.github.schema import GitHubReviewComment
from code_reviewer.guardrail import _scan_string, check_findings


def _comment(body: str) -> GitHubReviewComment:
    return GitHubReviewComment(path="a.py", line=1, body=body)


def _gitleaks_hit(description: str = "AWS Access Key") -> CompletedProcess:
    return CompletedProcess(
        args=[],
        returncode=1,
        stdout=json.dumps([{"Description": description}]),
        stderr="",
    )


_GITLEAKS_CLEAN = CompletedProcess(args=[], returncode=0, stdout="[]", stderr="")


# ---------------------------------------------------------------------------
# Unit tests (mocked subprocess)
# ---------------------------------------------------------------------------


class TestCheckFindings:
    def test_empty_findings(self):
        result = check_findings([])
        assert result.safe is True

    @patch("code_reviewer.guardrail.shutil.which", return_value=None)
    def test_skips_when_gitleaks_not_installed(self, _):
        result = check_findings([_comment("anything")])
        assert result.safe is True

    @patch("code_reviewer.guardrail.subprocess.run", return_value=_GITLEAKS_CLEAN)
    @patch("code_reviewer.guardrail.shutil.which", return_value="/usr/local/bin/gitleaks")
    def test_clean_finding(self, _w, _r):
        result = check_findings([_comment("normal code review")])
        assert result.safe is True

    @patch("code_reviewer.guardrail.subprocess.run", return_value=_gitleaks_hit("AWS Access Key"))
    @patch("code_reviewer.guardrail.shutil.which", return_value="/usr/local/bin/gitleaks")
    def test_flags_secret(self, _w, _r):
        result = check_findings([_comment("key: AKIAIOSFODNN7EXAMPLE")])
        assert result.safe is False
        assert result.flagged_indices == [0]
        assert "AWS" in result.reasons[0]

    @patch("code_reviewer.guardrail.shutil.which", return_value="/usr/local/bin/gitleaks")
    def test_mixed_findings(self, _w):
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                return _gitleaks_hit("Private Key")
            return _GITLEAKS_CLEAN

        with patch("code_reviewer.guardrail.subprocess.run", side_effect=side_effect):
            result = check_findings([_comment("clean"), _comment("secret"), _comment("clean")])
        assert result.flagged_indices == [1]

    @patch("code_reviewer.guardrail.shutil.which", return_value="/usr/local/bin/gitleaks")
    def test_handles_timeout(self, _w):
        import subprocess as sp

        with patch(
            "code_reviewer.guardrail.subprocess.run", side_effect=sp.TimeoutExpired("gitleaks", 10)
        ):
            result = check_findings([_comment("anything")])
        assert result.safe is True

    @patch("code_reviewer.guardrail.shutil.which", return_value="/usr/local/bin/gitleaks")
    def test_handles_bad_json(self, _w):
        bad = CompletedProcess(args=[], returncode=1, stdout="not json", stderr="")
        with patch("code_reviewer.guardrail.subprocess.run", return_value=bad):
            result = check_findings([_comment("anything")])
        assert result.safe is True


# ---------------------------------------------------------------------------
# Integration tests (require gitleaks installed)
# ---------------------------------------------------------------------------

_has_gitleaks = shutil.which("gitleaks") is not None
requires_gitleaks = pytest.mark.skipif(not _has_gitleaks, reason="gitleaks not installed")


@requires_gitleaks
class TestGitleaksIntegration:
    """Parametrized tests that actually call gitleaks."""

    @pytest.mark.parametrize(
        "body, should_flag",
        [
            # Secrets that should be flagged
            (
                "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA0Z3VS5JJcds3xfn/ygWyF"
                "5c13m2P8VMQP++7N9rRaJFBh+EA\nFAKEKEYDATA=\n-----END RSA PRIVATE KEY-----",
                True,
            ),
            # Clean findings that should NOT be flagged
            ("Use `os.getenv('API_KEY')` instead of hardcoding.", False),
            ("The `password` variable is not validated.", False),
            ("Check `GITHUB_TOKEN` is set in CI.", False),
            ("Replace `sk-...` with your actual key.", False),
            ("Missing error handling in `authenticate()` method.", False),
            ("The `api_key` parameter should be typed as `str | None`.", False),
            ("SQL injection in `query = f'SELECT * FROM {table}'`", False),
            ("Race condition: `self.count += 1` is not thread-safe.", False),
            ("Null check missing: `user.email` can be None when `is_anonymous=True`.", False),
        ],
        ids=[
            "private-key",
            "env-var-reference",
            "password-variable",
            "token-variable",
            "placeholder",
            "error-handling",
            "type-hint",
            "sql-injection",
            "race-condition",
            "null-check",
        ],
    )
    def test_scan(self, body, should_flag):
        leaks = _scan_string(body)
        if should_flag:
            assert len(leaks) > 0, f"Expected gitleaks to flag: {body[:60]}"
        else:
            assert len(leaks) == 0, f"False positive on: {body[:60]}"

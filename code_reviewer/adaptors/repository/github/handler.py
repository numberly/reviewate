"""GitHub repository handler — uses gh CLI for all platform operations."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
import zipfile

from pydantic import BaseModel

from code_reviewer.adaptors.repository.github.schema import GitHubReviewComment
from code_reviewer.adaptors.repository.handler import RepositoryHandler
from code_reviewer.adaptors.repository.schema import PostFailure, PostResult, Review

logger = logging.getLogger(__name__)


class GitHubHandler(RepositoryHandler):
    """GitHub platform handler using the gh CLI."""

    @property
    def platform_name(self) -> str:
        return "github"

    def validate_pr(self, repo: str, pr: str, env: dict[str, str]) -> str:
        result = subprocess.run(
            ["gh", "pr", "view", pr, "-R", repo, "--json", "state,title", "-q", ".title"],
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            raise RuntimeError(f"Failed to validate github PR #{pr}: {stderr}")
        return result.stdout.strip()

    def download_source(self, repo: str, pr: str, workspace: str, env: dict[str, str]) -> None:
        # Get the PR head SHA
        result = subprocess.run(
            ["gh", "pr", "view", pr, "-R", repo, "--json", "headRefOid", "-q", ".headRefOid"],
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            raise RuntimeError(f"Failed to get PR #{pr} head ref: {stderr}")
        sha = result.stdout.strip()

        # Download the zipball
        parent = os.path.dirname(workspace)
        zip_path = os.path.join(parent, "archive.zip")
        with open(zip_path, "wb") as f:
            dl_result = subprocess.run(
                ["gh", "api", f"repos/{repo}/zipball/{sha}"],
                stdout=f,
                stderr=subprocess.PIPE,
                text=False,
                timeout=240,
                env=env,
            )
        if dl_result.returncode != 0:
            stderr = dl_result.stderr.decode().strip()
            raise RuntimeError(f"Failed to download {repo} archive: {stderr}")

        # Extract and move to target workspace
        extract_dir = os.path.join(parent, "_extract")
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(extract_dir)
        os.remove(zip_path)

        # GitHub zipball creates a single top-level directory (owner-repo-sha)
        entries = os.listdir(extract_dir)
        if len(entries) == 1 and os.path.isdir(os.path.join(extract_dir, entries[0])):
            os.rename(os.path.join(extract_dir, entries[0]), workspace)
            os.rmdir(extract_dir)
        else:
            os.rename(extract_dir, workspace)

    def post_review(
        self,
        review: Review,
        repo: str,
        pr: str,
        env: dict[str, str],
        *,
        timeout: int = 30,
    ) -> PostResult:
        if not review.comments:
            return PostResult()

        inline = [c for c in review.comments if c.line is not None]
        fallback = [c for c in review.comments if c.line is None]
        result = PostResult()

        # Post inline comments as a single batch review
        if inline:
            review_payload = {
                "event": "COMMENT",
                "comments": [
                    {
                        "path": c.path,
                        "line": c.line,
                        "side": (c.side or "RIGHT").upper(),
                        "body": c.body,
                    }
                    for c in inline
                ],
            }

            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
                json.dump(review_payload, tmp)
                tmp_path = tmp.name

            cmd = [
                "gh",
                "api",
                f"repos/{repo}/pulls/{pr}/reviews",
                "--method",
                "POST",
                "--input",
                tmp_path,
            ]
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
            )

            if proc.returncode == 0:
                result.posted += len(inline)
                logger.info("Posted %d inline comments to GitHub", len(inline))
            else:
                error = proc.stderr.strip()
                logger.warning(
                    "GitHub batch review failed: %s — falling back to individual comments",
                    error,
                )
                for c in inline:
                    self._post_single(c, repo, pr, env, timeout, result)

        # Post comments without line numbers as regular PR comments
        for c in fallback:
            self._post_as_regular(c, repo, pr, env, timeout, result)

        return result

    def post_regular_comment(
        self,
        comment: BaseModel,
        repo: str,
        pr: str,
        env: dict[str, str],
        *,
        timeout: int = 30,
    ) -> bool:
        body = comment.body  # type: ignore[attr-defined]
        path = getattr(comment, "path", "unknown")
        cmd = ["gh", "pr", "comment", pr, "-R", repo, "--body", body]

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        if proc.returncode != 0:
            logger.warning("Failed to post comment for %s: %s", path, proc.stderr.strip())
        return proc.returncode == 0

    def fetch_discussions(self, repo: str, pr: str, env: dict[str, str]) -> list[dict]:
        discussions: list[dict] = []

        # Fetch review comments (inline) and issue comments (general)
        for endpoint in [f"repos/{repo}/pulls/{pr}/comments", f"repos/{repo}/issues/{pr}/comments"]:
            result = subprocess.run(
                ["gh", "api", endpoint, "--paginate"],
                capture_output=True,
                text=True,
                timeout=30,
                env=env,
            )
            if result.returncode != 0:
                logger.warning("Failed to fetch %s: %s", endpoint, result.stderr.strip())
                continue
            try:
                for comment in json.loads(result.stdout):
                    discussions.append(
                        {
                            "author": comment.get("user", {}).get("login", "unknown"),
                            "body": comment.get("body", ""),
                            "path": comment.get("path"),
                        }
                    )
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning("Failed to parse %s response: %s", endpoint, e)

        return discussions

    def get_diff_command(self, repo: str, pr: str) -> str:
        return f"gh pr diff {pr} -R {repo}"

    def fetch_pr_body(self, repo: str, pr: str, env: dict[str, str]) -> str:
        result = subprocess.run(
            ["gh", "pr", "view", pr, "-R", repo, "--json", "title,body,labels"],
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
        if result.returncode != 0:
            logger.warning("Failed to fetch PR body: %s", result.stderr.strip())
            return ""
        try:
            data = json.loads(result.stdout)
            parts = [f"# {data.get('title', '')}"]
            body = data.get("body", "")
            if body:
                parts.append(body)
            labels = data.get("labels", [])
            if labels:
                label_names = [lb.get("name", "") for lb in labels if lb.get("name")]
                if label_names:
                    parts.append(f"Labels: {', '.join(label_names)}")
            return "\n\n".join(parts)
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning("Failed to parse PR body: %s", e)
            return ""

    def fetch_diff(self, repo: str, pr: str, env: dict[str, str]) -> str:
        from code_reviewer.diffn import format_diff_with_line_numbers

        result = subprocess.run(
            ["gh", "pr", "diff", pr, "-R", repo],
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
        )
        if result.returncode != 0:
            logger.warning("Failed to fetch diff: %s", result.stderr.strip())
            return ""
        return format_diff_with_line_numbers(result.stdout)

    @property
    def comment_model(self) -> type[BaseModel]:
        return GitHubReviewComment

    @property
    def review_schema(self) -> type[Review]:
        return Review[GitHubReviewComment]

    # -- private helpers --

    def _post_single(
        self,
        comment: GitHubReviewComment,
        repo: str,
        pr: str,
        env: dict[str, str],
        timeout: int,
        result: PostResult,
    ) -> None:
        """Post a single inline comment as an individual GitHub review."""
        review_payload = {
            "event": "COMMENT",
            "comments": [
                {
                    "path": comment.path,
                    "line": comment.line,
                    "side": (comment.side or "RIGHT").upper(),
                    "body": comment.body,
                }
            ],
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            json.dump(review_payload, tmp)
            tmp_path = tmp.name

        cmd = [
            "gh",
            "api",
            f"repos/{repo}/pulls/{pr}/reviews",
            "--method",
            "POST",
            "--input",
            tmp_path,
        ]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        if proc.returncode == 0:
            result.posted += 1
        else:
            result.failed.append(PostFailure(comment=comment, error=proc.stderr.strip()))

    def _post_as_regular(
        self,
        comment: BaseModel,
        repo: str,
        pr: str,
        env: dict[str, str],
        timeout: int,
        result: PostResult,
    ) -> None:
        """Post a comment as a regular (non-inline) PR comment."""
        body = comment.body  # type: ignore[attr-defined]
        cmd = ["gh", "pr", "comment", pr, "-R", repo, "--body", body]

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        if proc.returncode == 0:
            result.posted += 1
        else:
            result.failed.append(PostFailure(comment=comment, error=proc.stderr.strip()))

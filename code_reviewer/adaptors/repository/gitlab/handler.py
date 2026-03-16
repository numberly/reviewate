"""GitLab repository handler — uses glab CLI for all platform operations."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
import zipfile

from pydantic import BaseModel

from code_reviewer.adaptors.repository.gitlab.schema import GitLabReviewComment
from code_reviewer.adaptors.repository.handler import RepositoryHandler
from code_reviewer.adaptors.repository.schema import PostFailure, PostResult, Review

logger = logging.getLogger(__name__)


class GitLabHandler(RepositoryHandler):
    """GitLab platform handler using the glab CLI."""

    @property
    def platform_name(self) -> str:
        return "gitlab"

    def validate_pr(self, repo: str, pr: str, env: dict[str, str]) -> str:
        result = subprocess.run(
            ["glab", "mr", "view", pr, "-R", repo, "--output", "json"],
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            raise RuntimeError(f"Failed to validate gitlab MR #{pr}: {stderr}")
        return result.stdout.strip()

    def download_source(self, repo: str, pr: str, workspace: str, env: dict[str, str]) -> None:
        # Get the MR source branch SHA
        result = subprocess.run(
            ["glab", "mr", "view", pr, "-R", repo, "--output", "json"],
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            raise RuntimeError(f"Failed to get MR #{pr} info: {stderr}")

        try:
            mr_info = json.loads(result.stdout)
            sha = mr_info["sha"]
        except (json.JSONDecodeError, KeyError) as e:
            raise RuntimeError(f"Failed to parse MR info: {e}") from e

        # Download the archive via glab api (binary output captured as bytes)
        project_id = repo.replace("/", "%2F")
        dl_result = subprocess.run(
            ["glab", "api", f"projects/{project_id}/repository/archive.zip?sha={sha}"],
            capture_output=True,
            timeout=240,
            env=env,
        )
        if dl_result.returncode != 0:
            stderr = (
                dl_result.stderr.decode()
                if isinstance(dl_result.stderr, bytes)
                else dl_result.stderr
            )
            raise RuntimeError(f"Failed to download {repo} archive: {stderr.strip()}")

        # Write the binary response to a zip file
        parent = os.path.dirname(workspace)
        zip_path = os.path.join(parent, "archive.zip")
        with open(zip_path, "wb") as f:
            f.write(dl_result.stdout)

        # Extract and move to target workspace
        extract_dir = os.path.join(parent, "_extract")
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(extract_dir)
        os.remove(zip_path)

        # GitLab archive creates a single top-level directory (repo-branch-sha)
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

        result = PostResult()
        project_id = repo.replace("/", "%2F")

        # Fetch SHAs from the versions API
        versions_cmd = [
            "glab",
            "api",
            f"projects/{project_id}/merge_requests/{pr}/versions",
        ]
        proc = subprocess.run(
            versions_cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        if proc.returncode != 0:
            error = proc.stderr.strip()
            logger.warning("Failed to fetch GitLab MR versions: %s", error)
            for c in review.comments:
                result.failed.append(PostFailure(comment=c, error=error))
            return result

        try:
            versions = json.loads(proc.stdout)
            latest = versions[0]
            base_sha = latest["base_commit_sha"]
            head_sha = latest["head_commit_sha"]
            start_sha = latest["start_commit_sha"]
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            error = f"Failed to parse versions response: {e}"
            logger.warning(error)
            for c in review.comments:
                result.failed.append(PostFailure(comment=c, error=error))
            return result

        # Split inline vs fallback
        inline = [c for c in review.comments if c.new_line is not None or c.old_line is not None]
        fallback = [c for c in review.comments if c.new_line is None and c.old_line is None]

        # Post each inline comment as a diff note
        for c in inline:
            position: dict = {
                "position_type": "text",
                "base_sha": base_sha,
                "head_sha": head_sha,
                "start_sha": start_sha,
                "new_path": c.new_path,
                "old_path": c.old_path or c.new_path,
            }

            if c.old_line is not None:
                position["old_line"] = c.old_line
            if c.new_line is not None:
                position["new_line"] = c.new_line

            note_payload = {
                "body": c.body,
                "position": position,
            }

            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
                json.dump(note_payload, tmp)
                tmp_path = tmp.name

            cmd = [
                "glab",
                "api",
                f"projects/{project_id}/merge_requests/{pr}/discussions",
                "--method",
                "POST",
                "--input",
                tmp_path,
                "-H",
                "Content-Type: application/json",
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
                result.failed.append(PostFailure(comment=c, error=proc.stderr.strip()))

        # Post comments without line numbers as regular MR notes
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
        path = getattr(comment, "new_path", "unknown")
        cmd = ["glab", "mr", "note", pr, "-R", repo, "-m", body]

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
        project_id = repo.replace("/", "%2F")
        result = subprocess.run(
            ["glab", "api", f"projects/{project_id}/merge_requests/{pr}/notes", "--paginate"],
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
        if result.returncode != 0:
            logger.warning("Failed to fetch MR notes: %s", result.stderr.strip())
            return []

        discussions: list[dict] = []
        try:
            for note in json.loads(result.stdout):
                if note.get("system", False):
                    continue
                discussions.append(
                    {
                        "author": note.get("author", {}).get("username", "unknown"),
                        "body": note.get("body", ""),
                    }
                )
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning("Failed to parse MR notes response: %s", e)

        return discussions

    def get_diff_command(self, repo: str, pr: str) -> str:
        return f"glab mr diff {pr} -R {repo}"

    def fetch_pr_body(self, repo: str, pr: str, env: dict[str, str]) -> str:
        result = subprocess.run(
            ["glab", "mr", "view", pr, "-R", repo, "--output", "json"],
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
        if result.returncode != 0:
            logger.warning("Failed to fetch MR body: %s", result.stderr.strip())
            return ""
        try:
            data = json.loads(result.stdout)
            parts = [f"# {data.get('title', '')}"]
            description = data.get("description", "")
            if description:
                parts.append(description)
            labels = data.get("labels", [])
            if labels:
                parts.append(f"Labels: {', '.join(labels)}")
            return "\n\n".join(parts)
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning("Failed to parse MR body: %s", e)
            return ""

    def fetch_diff(self, repo: str, pr: str, env: dict[str, str]) -> str:
        from code_reviewer.diffn import format_diff_with_line_numbers

        result = subprocess.run(
            ["glab", "mr", "diff", pr, "-R", repo],
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
        return GitLabReviewComment

    @property
    def review_schema(self) -> type[Review]:
        return Review[GitLabReviewComment]

    # -- private helpers --

    def _post_as_regular(
        self,
        comment: BaseModel,
        repo: str,
        pr: str,
        env: dict[str, str],
        timeout: int,
        result: PostResult,
    ) -> None:
        """Post a comment as a regular (non-inline) MR note."""
        body = comment.body  # type: ignore[attr-defined]
        cmd = ["glab", "mr", "note", pr, "-R", repo, "-m", body]

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

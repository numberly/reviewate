"""Lightweight HTTP utilities for PR/MR comment CRUD.

Manages bot comments on GitHub PRs and GitLab MRs using marker-based
identification (HTML comments like <!-- reviewate-status -->).
"""

import logging
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

# Timeout for comment API calls (seconds)
_TIMEOUT = 15


async def upsert_bot_comment(
    platform: str,
    api_url: str,
    token: str,
    repo: str,
    merge_id: str | int,
    marker: str,
    body: str,
) -> None:
    """Find a comment containing marker and edit it, or create a new one.

    Args:
        platform: "github" or "gitlab"
        api_url: API base URL (e.g. "https://api.github.com" or "https://gitlab.com/api/v4")
        token: Platform access token
        repo: Repository path (e.g. "owner/repo")
        merge_id: PR number (GitHub) or MR IID (GitLab)
        marker: HTML comment marker to identify the bot comment
        body: Full comment body (should include the marker)
    """
    if platform == "github":
        await _upsert_github_comment(api_url, token, repo, merge_id, marker, body)
    elif platform == "gitlab":
        await _upsert_gitlab_comment(api_url, token, repo, merge_id, marker, body)
    else:
        logger.warning(f"Unsupported platform for comments: {platform}")


async def _upsert_github_comment(
    api_url: str,
    token: str,
    repo: str,
    merge_id: str | int,
    marker: str,
    body: str,
) -> None:
    """Upsert a comment on a GitHub PR (issues API)."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Reviewate",
    }

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        # Fetch existing comments (paginated, scan for marker)
        comment_id = await _find_github_comment(client, api_url, repo, merge_id, marker, headers)

        if comment_id is not None:
            # Edit existing comment
            url = f"{api_url}/repos/{repo}/issues/comments/{comment_id}"
            resp = await client.patch(url, headers=headers, json={"body": body})
            resp.raise_for_status()
            logger.debug(f"Updated GitHub comment {comment_id} on {repo}#{merge_id}")
        else:
            # Create new comment
            url = f"{api_url}/repos/{repo}/issues/{merge_id}/comments"
            resp = await client.post(url, headers=headers, json={"body": body})
            resp.raise_for_status()
            logger.debug(f"Created GitHub comment on {repo}#{merge_id}")


async def _find_github_comment(
    client: httpx.AsyncClient,
    api_url: str,
    repo: str,
    merge_id: str | int,
    marker: str,
    headers: dict[str, str],
) -> int | None:
    """Scan GitHub issue comments for one containing the marker."""
    page = 1
    while True:
        url = f"{api_url}/repos/{repo}/issues/{merge_id}/comments"
        resp = await client.get(url, headers=headers, params={"page": page, "per_page": 100})
        resp.raise_for_status()
        comments = resp.json()

        if not comments:
            break

        for comment in comments:
            if marker in (comment.get("body") or ""):
                return comment["id"]

        if len(comments) < 100:
            break
        page += 1

    return None


async def _upsert_gitlab_comment(
    api_url: str,
    token: str,
    repo: str,
    merge_id: str | int,
    marker: str,
    body: str,
) -> None:
    """Upsert a comment (note) on a GitLab MR."""
    headers = {"PRIVATE-TOKEN": token}
    encoded_repo = quote(repo, safe="")

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        # Fetch existing notes (paginated, scan for marker)
        note_id = await _find_gitlab_note(client, api_url, encoded_repo, merge_id, marker, headers)

        if note_id is not None:
            # Edit existing note
            url = f"{api_url}/projects/{encoded_repo}/merge_requests/{merge_id}/notes/{note_id}"
            resp = await client.put(url, headers=headers, json={"body": body})
            resp.raise_for_status()
            logger.debug(f"Updated GitLab note {note_id} on {repo}!{merge_id}")
        else:
            # Create new note
            url = f"{api_url}/projects/{encoded_repo}/merge_requests/{merge_id}/notes"
            resp = await client.post(url, headers=headers, json={"body": body})
            resp.raise_for_status()
            logger.debug(f"Created GitLab note on {repo}!{merge_id}")


async def _find_gitlab_note(
    client: httpx.AsyncClient,
    api_url: str,
    encoded_repo: str,
    merge_id: str | int,
    marker: str,
    headers: dict[str, str],
) -> int | None:
    """Scan GitLab MR notes for one containing the marker."""
    page = 1
    while True:
        url = f"{api_url}/projects/{encoded_repo}/merge_requests/{merge_id}/notes"
        resp = await client.get(url, headers=headers, params={"page": page, "per_page": 100})
        resp.raise_for_status()
        notes = resp.json()

        if not notes:
            break

        for note in notes:
            if marker in (note.get("body") or ""):
                return note["id"]

        if len(notes) < 100:
            break
        page += 1

    return None

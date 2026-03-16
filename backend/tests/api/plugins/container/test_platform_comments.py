"""Tests for platform_comments module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.plugins.container.platform_comments import upsert_bot_comment

MARKER = "<!-- reviewate-status -->"


def _mock_response(status_code=200, json_data=None):
    """Create a mock httpx response that supports raise_for_status."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    return resp


def _mock_httpx_client():
    """Create a mock httpx.AsyncClient context manager."""
    client = AsyncMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=client)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm, client


# --- GitHub ---


@pytest.mark.asyncio
async def test_github_creates_new_comment_when_none_exists():
    """When no comment with marker exists, create a new one."""
    cm, client = _mock_httpx_client()
    client.get = AsyncMock(return_value=_mock_response(200, []))
    client.post = AsyncMock(return_value=_mock_response(201, {"id": 1}))

    with patch("api.plugins.container.platform_comments.httpx.AsyncClient", return_value=cm):
        await upsert_bot_comment(
            platform="github",
            api_url="https://api.github.com",
            token="ghp_test",
            repo="owner/repo",
            merge_id=42,
            marker=MARKER,
            body=f"{MARKER}\nRunning: review",
        )

    client.post.assert_called_once()
    assert "/issues/42/comments" in client.post.call_args.args[0]


@pytest.mark.asyncio
async def test_github_edits_existing_comment():
    """When a comment with marker exists, edit it."""
    cm, client = _mock_httpx_client()
    client.get = AsyncMock(return_value=_mock_response(200, [{"id": 99, "body": f"{MARKER}\nOld"}]))
    client.patch = AsyncMock(return_value=_mock_response(200, {"id": 99}))

    with patch("api.plugins.container.platform_comments.httpx.AsyncClient", return_value=cm):
        await upsert_bot_comment(
            platform="github",
            api_url="https://api.github.com",
            token="ghp_test",
            repo="owner/repo",
            merge_id=42,
            marker=MARKER,
            body=f"{MARKER}\nUpdated",
        )

    client.patch.assert_called_once()
    assert "/issues/comments/99" in client.patch.call_args.args[0]


@pytest.mark.asyncio
async def test_github_paginates_to_find_comment():
    """Should paginate through comments to find marker."""
    page1 = [{"id": i, "body": "unrelated"} for i in range(100)]
    page2 = [{"id": 200, "body": f"{MARKER}\nOld"}]

    cm, client = _mock_httpx_client()
    client.get = AsyncMock(side_effect=[_mock_response(200, page1), _mock_response(200, page2)])
    client.patch = AsyncMock(return_value=_mock_response(200, {"id": 200}))

    with patch("api.plugins.container.platform_comments.httpx.AsyncClient", return_value=cm):
        await upsert_bot_comment(
            platform="github",
            api_url="https://api.github.com",
            token="ghp_test",
            repo="owner/repo",
            merge_id=42,
            marker=MARKER,
            body=f"{MARKER}\nUpdated",
        )

    assert client.get.call_count == 2
    client.patch.assert_called_once()


# --- GitLab ---


@pytest.mark.asyncio
async def test_gitlab_creates_new_note_when_none_exists():
    """When no note with marker exists, create a new one."""
    cm, client = _mock_httpx_client()
    client.get = AsyncMock(return_value=_mock_response(200, []))
    client.post = AsyncMock(return_value=_mock_response(201, {"id": 1}))

    with patch("api.plugins.container.platform_comments.httpx.AsyncClient", return_value=cm):
        await upsert_bot_comment(
            platform="gitlab",
            api_url="https://gitlab.com/api/v4",
            token="glpat-test",
            repo="group/project",
            merge_id=7,
            marker=MARKER,
            body=f"{MARKER}\nRunning: review",
        )

    client.post.assert_called_once()
    assert "/notes" in client.post.call_args.args[0]


@pytest.mark.asyncio
async def test_gitlab_edits_existing_note():
    """When a note with marker exists, edit it."""
    cm, client = _mock_httpx_client()
    client.get = AsyncMock(return_value=_mock_response(200, [{"id": 55, "body": f"{MARKER}\nOld"}]))
    client.put = AsyncMock(return_value=_mock_response(200, {"id": 55}))

    with patch("api.plugins.container.platform_comments.httpx.AsyncClient", return_value=cm):
        await upsert_bot_comment(
            platform="gitlab",
            api_url="https://gitlab.com/api/v4",
            token="glpat-test",
            repo="group/project",
            merge_id=7,
            marker=MARKER,
            body=f"{MARKER}\nUpdated",
        )

    client.put.assert_called_once()
    assert "/notes/55" in client.put.call_args.args[0]


# --- Unsupported ---


@pytest.mark.asyncio
async def test_unsupported_platform_logs_warning(caplog):
    """Should log warning for unsupported platform."""
    await upsert_bot_comment(
        platform="bitbucket",
        api_url="https://api.bitbucket.org",
        token="tok",
        repo="owner/repo",
        merge_id=1,
        marker=MARKER,
        body="test",
    )
    assert "Unsupported platform" in caplog.text

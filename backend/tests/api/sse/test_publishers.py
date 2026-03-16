"""Tests for SSE publishers."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from api.routers.organizations.schemas import OrganizationEventMessage
from api.routers.pull_requests.schemas import PullRequestEventMessage
from api.routers.repositories.schemas import RepositoryEventMessage
from api.sse.publishers import (
    publish_organization_event,
    publish_pull_request_event,
    publish_repository_event,
)
from tests.utils.factories import (
    PullRequestEventMessageFactory,
)


@pytest.mark.asyncio
@patch("api.sse.publishers.get_faststream_broker")
async def test_publish_organization_event_success(mock_get_broker: MagicMock):
    """Test publishing organization event successfully."""
    # Setup
    mock_broker = MagicMock()
    mock_broker.publish = AsyncMock(return_value=None)
    mock_get_broker.return_value = mock_broker

    # Use factory-generated data pattern for organization dict
    user_id = str(uuid4())
    org_id = str(uuid4())
    organization = {
        "id": org_id,
        "name": "Test Org",
        "provider": "github",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-02T00:00:00Z",
    }

    # Execute
    await publish_organization_event(
        user_id=user_id,
        action="created",
        organization=organization,
    )

    # Verify
    mock_broker.publish.assert_called_once()
    call_args = mock_broker.publish.call_args

    # Check message is a proper Pydantic schema
    message = call_args[0][0]
    assert isinstance(message, OrganizationEventMessage)
    assert message.user_id == user_id
    assert message.action == "created"
    assert message.organization == organization
    assert message.timestamp == "2024-01-02T00:00:00Z"  # Uses updated_at

    # Check channel
    assert call_args[1]["channel"] == "reviewate.events.organizations"


@pytest.mark.asyncio
@patch("api.sse.publishers.get_faststream_broker")
async def test_publish_organization_event_uses_created_at_fallback(mock_get_broker: MagicMock):
    """Test that organization event uses created_at when updated_at is missing."""
    # Setup
    mock_broker = MagicMock()
    mock_broker.publish = AsyncMock(return_value=None)
    mock_get_broker.return_value = mock_broker

    user_id = str(uuid4())
    organization = {
        "id": str(uuid4()),
        "name": "Test Org",
        "created_at": "2024-01-01T00:00:00Z",
        # No updated_at
    }

    # Execute
    await publish_organization_event(
        user_id=user_id,
        action="created",
        organization=organization,
    )

    # Verify
    message = mock_broker.publish.call_args[0][0]
    assert isinstance(message, OrganizationEventMessage)
    assert message.timestamp == "2024-01-01T00:00:00Z"  # Falls back to created_at


@pytest.mark.asyncio
@patch("api.sse.publishers.get_faststream_broker")
async def test_publish_organization_event_handles_error(mock_get_broker: MagicMock):
    """Test that organization event handles broker errors gracefully."""
    # Setup
    mock_broker = MagicMock()
    mock_broker.publish = AsyncMock(side_effect=Exception("Broker error"))
    mock_get_broker.return_value = mock_broker

    organization = {"id": str(uuid4()), "name": "Test Org"}

    # Execute - should not raise
    await publish_organization_event(
        user_id=str(uuid4()),
        action="created",
        organization=organization,
    )

    # Verify publish was attempted
    mock_broker.publish.assert_called_once()


@pytest.mark.asyncio
@patch("api.sse.publishers.get_faststream_broker")
async def test_publish_repository_event_success(mock_get_broker: MagicMock):
    """Test publishing repository event successfully."""
    # Setup
    mock_broker = MagicMock()
    mock_broker.publish = AsyncMock(return_value=None)
    mock_get_broker.return_value = mock_broker

    org_id = str(uuid4())
    repo_id = str(uuid4())
    repository = {
        "id": repo_id,
        "name": "test-repo",
        "external_repo_id": "12345",
        "web_url": "https://github.com/test-org/test-repo",
        "provider": "github",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-02T00:00:00Z",
    }

    # Execute
    await publish_repository_event(
        organization_id=org_id,
        action="updated",
        repository=repository,
    )

    # Verify
    mock_broker.publish.assert_called_once()
    call_args = mock_broker.publish.call_args

    # Check message is a proper Pydantic schema
    message = call_args[0][0]
    assert isinstance(message, RepositoryEventMessage)
    assert message.organization_id == org_id
    assert message.action == "updated"
    assert message.repository == repository
    assert message.timestamp == "2024-01-02T00:00:00Z"

    # Check channel
    assert call_args[1]["channel"] == "reviewate.events.repositories"


@pytest.mark.asyncio
@patch("api.sse.publishers.get_faststream_broker")
async def test_publish_repository_event_uses_created_at_fallback(mock_get_broker: MagicMock):
    """Test that repository event uses created_at when updated_at is missing."""
    # Setup
    mock_broker = MagicMock()
    mock_broker.publish = AsyncMock(return_value=None)
    mock_get_broker.return_value = mock_broker

    repository = {
        "id": str(uuid4()),
        "name": "test-repo",
        "created_at": "2024-01-01T00:00:00Z",
    }

    # Execute
    await publish_repository_event(
        organization_id=str(uuid4()),
        action="created",
        repository=repository,
    )

    # Verify
    message = mock_broker.publish.call_args[0][0]
    assert isinstance(message, RepositoryEventMessage)
    assert message.timestamp == "2024-01-01T00:00:00Z"


@pytest.mark.asyncio
@patch("api.sse.publishers.get_faststream_broker")
async def test_publish_repository_event_handles_error(mock_get_broker: MagicMock):
    """Test that repository event handles broker errors gracefully."""
    # Setup
    mock_broker = MagicMock()
    mock_broker.publish = AsyncMock(side_effect=Exception("Broker error"))
    mock_get_broker.return_value = mock_broker

    repository = {"id": str(uuid4()), "name": "test-repo"}

    # Execute - should not raise
    await publish_repository_event(
        organization_id=str(uuid4()),
        action="created",
        repository=repository,
    )

    # Verify publish was attempted
    mock_broker.publish.assert_called_once()


@pytest.mark.asyncio
@patch("api.sse.publishers.get_faststream_broker")
async def test_publish_pull_request_event_success(mock_get_broker: MagicMock):
    """Test publishing pull request event successfully."""
    # Setup
    mock_broker = MagicMock()
    mock_broker.publish = AsyncMock(return_value=None)
    mock_get_broker.return_value = mock_broker

    # Use factory to generate test data
    expected_message = PullRequestEventMessageFactory.build(
        action="execution_status_changed",
    )

    # Execute
    await publish_pull_request_event(
        pull_request_id=expected_message.pull_request_id,
        action=expected_message.action,
        organization_id=expected_message.organization_id,
        repository_id=expected_message.repository_id,
        latest_execution_id=expected_message.latest_execution_id,
        latest_execution_status=expected_message.latest_execution_status,
        latest_execution_created_at=expected_message.latest_execution_created_at,
        updated_at=expected_message.updated_at,
    )

    # Verify
    mock_broker.publish.assert_called_once()
    call_args = mock_broker.publish.call_args

    # Check message is a proper Pydantic schema
    message = call_args[0][0]
    assert isinstance(message, PullRequestEventMessage)
    assert message.pull_request_id == expected_message.pull_request_id
    assert message.action == "execution_status_changed"
    assert message.organization_id == expected_message.organization_id
    assert message.repository_id == expected_message.repository_id
    assert message.latest_execution_id == expected_message.latest_execution_id
    assert message.latest_execution_status == expected_message.latest_execution_status

    # Check channel
    assert call_args[1]["channel"] == "reviewate.events.pull_requests"


@pytest.mark.asyncio
@patch("api.sse.publishers.get_faststream_broker")
async def test_publish_pull_request_event_handles_error(mock_get_broker: MagicMock):
    """Test that pull request event handles broker errors gracefully."""
    # Setup
    mock_broker = MagicMock()
    mock_broker.publish = AsyncMock(side_effect=Exception("Broker error"))
    mock_get_broker.return_value = mock_broker

    # Use factory to generate test data
    test_data = PullRequestEventMessageFactory.build()

    # Execute - should not raise
    await publish_pull_request_event(
        pull_request_id=test_data.pull_request_id,
        action=test_data.action,
        organization_id=test_data.organization_id,
        repository_id=test_data.repository_id,
    )

    # Verify publish was attempted
    mock_broker.publish.assert_called_once()

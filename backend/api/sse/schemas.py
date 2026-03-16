"""SSE event schemas and configuration.

Defines resource-specific SSE behavior patterns including terminal states
and event type configuration.
"""

from dataclasses import dataclass


@dataclass
class SSEEventSchema:
    """Configuration for resource-specific SSE behavior.

    Defines how SSE events should be handled for a specific resource type,
    including terminal states and event naming.

    Attributes:
        terminal_statuses: List of status values that end the stream
        event_type: SSE event type for status updates (default: "status")
        resource_id_field: Field name in event data containing the resource ID

    Example:
        >>> schema = SSEEventSchema(
        ...     terminal_statuses=["completed", "failed"],
        ...     event_type="status",
        ...     resource_id_field="execution_id"
        ... )
        >>> schema.is_terminal({"status": "completed"})
        True
    """

    terminal_statuses: list[str]
    event_type: str = "status"
    resource_id_field: str = "id"

    def is_terminal(self, data: dict) -> bool:
        """Check if event data represents a terminal state.

        Args:
            data: Event data dictionary

        Returns:
            True if the status is terminal, False otherwise
        """
        return data.get("status") in self.terminal_statuses


# Predefined schemas for common resource types

EXECUTION_SCHEMA = SSEEventSchema(
    terminal_statuses=["completed", "failed", "cancelled"],
    event_type="status",
    resource_id_field="execution_id",
)

PULL_REQUEST_SCHEMA = SSEEventSchema(
    terminal_statuses=["closed", "merged"],
    event_type="pr_update",
    resource_id_field="pull_request_id",
)

ORGANIZATION_SCHEMA = SSEEventSchema(
    terminal_statuses=[],
    event_type="org_update",
    resource_id_field="user_id",
)

REPOSITORY_SCHEMA = SSEEventSchema(
    terminal_statuses=[],
    event_type="repo_update",
    resource_id_field="organization_id",
)

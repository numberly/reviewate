"""Utility functions for GitLab source management."""

from fastapi import HTTPException


def extract_group_id_from_username(username: str) -> str:
    """Extract group ID from group bot username.

    Args:
        username: Bot username (format: group_{group_id}_bot_{hash})

    Returns:
        Group ID as string

    Raises:
        HTTPException: If username format is invalid
    """
    try:
        # Format: group_{group_id}_bot_{hash}
        parts = username.split("_")
        if len(parts) >= 4 and parts[0] == "group" and parts[2] == "bot":
            return parts[1]
        raise ValueError("Invalid group bot username format")
    except (ValueError, IndexError) as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid group token username format: {username}",
        ) from e


def extract_project_id_from_username(username: str) -> str:
    """Extract project ID from project bot username.

    Args:
        username: Bot username (format: project_{project_id}_bot_{hash})

    Returns:
        Project ID as string

    Raises:
        HTTPException: If username format is invalid
    """
    try:
        # Format: project_{project_id}_bot_{hash}
        parts = username.split("_")
        if len(parts) >= 4 and parts[0] == "project" and parts[2] == "bot":
            return parts[1]
        raise ValueError("Invalid project bot username format")
    except (ValueError, IndexError) as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid project token username format: {username}",
        ) from e

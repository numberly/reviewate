"""Repository handler factory."""

from __future__ import annotations

from code_reviewer.adaptors.repository.handler import RepositoryHandler


def get_handler(platform: str) -> RepositoryHandler:
    """Return the appropriate handler for the given platform."""
    match platform:
        case "github":
            from code_reviewer.adaptors.repository.github.handler import GitHubHandler

            return GitHubHandler()
        case "gitlab":
            from code_reviewer.adaptors.repository.gitlab.handler import GitLabHandler

            return GitLabHandler()
    raise ValueError(f"Unsupported platform: {platform}")


__all__ = ["RepositoryHandler", "get_handler"]

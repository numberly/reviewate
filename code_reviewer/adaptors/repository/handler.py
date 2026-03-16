"""Abstract base class for platform-specific repository handlers."""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel

from code_reviewer.adaptors.repository.schema import PostResult, Review


class RepositoryHandler(ABC):
    """ABC for platform-specific PR/MR operations.

    Each platform (GitHub, GitLab) implements this interface using
    its respective CLI tool (gh, glab) via subprocess calls.
    """

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Return the platform identifier (e.g., 'github', 'gitlab')."""
        ...

    @abstractmethod
    def validate_pr(self, repo: str, pr: str, env: dict[str, str]) -> str:
        """Validate the PR/MR exists and return its title. Raises on failure."""
        ...

    @abstractmethod
    def download_source(self, repo: str, pr: str, workspace: str, env: dict[str, str]) -> None:
        """Download the PR/MR source as a zip archive and extract it. Raises on failure."""
        ...

    @abstractmethod
    def post_review(
        self,
        review: Review,
        repo: str,
        pr: str,
        env: dict[str, str],
        *,
        timeout: int = 30,
    ) -> PostResult:
        """Post a Review's comments as inline review comments."""
        ...

    @abstractmethod
    def post_regular_comment(
        self,
        comment: BaseModel,
        repo: str,
        pr: str,
        env: dict[str, str],
        *,
        timeout: int = 30,
    ) -> bool:
        """Post a single comment as a regular (non-inline) comment."""
        ...

    @abstractmethod
    def fetch_discussions(self, repo: str, pr: str, env: dict[str, str]) -> list[dict]:
        """Fetch existing review discussions/comments from the PR/MR.

        Returns a list of dicts with at least 'author' and 'body' keys.
        """
        ...

    @abstractmethod
    def get_diff_command(self, repo: str, pr: str) -> str:
        """Return the shell command to get the numbered diff."""
        ...

    @abstractmethod
    def fetch_pr_body(self, repo: str, pr: str, env: dict[str, str]) -> str:
        """Fetch the PR/MR title, description, and labels as formatted text."""
        ...

    @abstractmethod
    def fetch_diff(self, repo: str, pr: str, env: dict[str, str]) -> str:
        """Fetch the diff with line numbers added."""
        ...

    @property
    @abstractmethod
    def comment_model(self) -> type[BaseModel]:
        """Return the platform-specific comment model class."""
        ...

    @property
    @abstractmethod
    def review_schema(self) -> type[Review]:
        """Return the parameterized Review type for the platform."""
        ...

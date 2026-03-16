"""GitLab API response schemas."""

from enum import StrEnum

from pydantic import BaseModel


class GitLabUser(BaseModel):
    """GitLab user response from /user endpoint."""

    id: int
    username: str
    email: str | None = None
    name: str | None = None
    avatar_url: str | None = None
    web_url: str


class GitlabTokenType(StrEnum):
    """Types of GitLab tokens."""

    PERSONAL_ACCESS_TOKEN = "personal_access_token"
    PROJECT_ACCESS_TOKEN = "project_access_token"
    GROUP_ACCESS_TOKEN = "group_access_token"

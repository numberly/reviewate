"""Schemas for GitHub sources endpoints."""

from pydantic import BaseModel, Field


class GitHubAppInstallUrl(BaseModel):
    """GitHub App installation URL response."""

    url: str
    app_name: str


class UninstallResponse(BaseModel):
    """Response for uninstall operation."""

    message: str = Field(description="Response message")
    success: bool = Field(description="Whether the operation succeeded")

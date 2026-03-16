"""Validation utilities for linked repositories."""

from dataclasses import dataclass
from urllib.parse import urlparse

from fastapi import HTTPException

from api.context import get_current_app
from api.models import Organization, Repository
from api.security import get_encryptor

from .schemas import LinkedRepositoryCreate


@dataclass
class ParsedRepoUrl:
    """Parsed components of a repository URL."""

    provider: str
    provider_url: str
    repo_path: str


def parse_repo_url(url: str) -> ParsedRepoUrl:
    """Parse a repository URL into its components.

    Args:
        url: Full repository URL (e.g., 'https://github.com/owner/repo')

    Returns:
        ParsedRepoUrl with provider, provider_url, and repo_path

    Raises:
        HTTPException: If the URL is invalid or malformed
    """
    try:
        parsed = urlparse(url.strip())
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid URL format.") from e

    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="URL must use http or https scheme.")

    if not parsed.hostname:
        raise HTTPException(status_code=400, detail="Invalid URL format.")

    host = parsed.hostname.lower()
    provider = "gitlab" if "gitlab" in host else "github"
    provider_url = f"{parsed.scheme}://{parsed.hostname}"
    if parsed.port and parsed.port not in (80, 443):
        provider_url = f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"

    # Extract repo path: full path stripped of leading/trailing slashes
    repo_path = parsed.path.strip("/")
    segments = repo_path.split("/")
    if len(segments) < 2 or not all(segments):
        raise HTTPException(
            status_code=400,
            detail="URL must contain at least owner and repository (e.g., 'owner/repo').",
        )

    return ParsedRepoUrl(provider=provider, provider_url=provider_url, repo_path=repo_path)


async def validate_linked_repo_access(
    data: LinkedRepositoryCreate,
    organization: Organization,
    repository: Repository | None = None,
) -> ParsedRepoUrl:
    """Parse the URL and validate access to the linked repository via the provider API.

    Returns:
        ParsedRepoUrl with the parsed components for storage.
    """
    parsed = parse_repo_url(data.url)

    app = get_current_app()

    if parsed.provider == "github":
        if not app.github:
            raise HTTPException(status_code=500, detail="GitHub plugin not configured.")
        if not organization.installation_id:
            raise HTTPException(
                status_code=422,
                detail="Organization does not have a GitHub App installation configured.",
            )
        await app.github.verify_repo_access(organization.installation_id, parsed.repo_path)
        await app.github.verify_branch_exists(
            organization.installation_id, parsed.repo_path, data.branch
        )

    elif parsed.provider == "gitlab":
        if not app.gitlab:
            raise HTTPException(status_code=500, detail="GitLab plugin not configured.")

        encrypted_token = None
        if repository and repository.gitlab_access_token_encrypted:
            encrypted_token = repository.gitlab_access_token_encrypted
        elif organization.gitlab_access_token_encrypted:
            encrypted_token = organization.gitlab_access_token_encrypted

        if not encrypted_token:
            raise HTTPException(
                status_code=422,
                detail="No GitLab access token configured for this organization or repository.",
            )

        access_token = get_encryptor().decrypt(encrypted_token)
        await app.gitlab.verify_repo_access(access_token, parsed.provider_url, parsed.repo_path)
        await app.gitlab.verify_branch_exists(
            access_token, parsed.provider_url, parsed.repo_path, data.branch
        )

    return parsed

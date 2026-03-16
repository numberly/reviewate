"""GitHub integration plugin.

Provides GitHub API functionality using BaseHttpPlugin.
Supports both user-to-server OAuth and GitHub App installation authentication.
"""

import logging
import time
from pathlib import Path

import jwt
from fastapi import HTTPException

from api.plugins.github.config import GitHubPluginConfig
from api.plugins.httpx.client import BaseHttpPlugin

logger = logging.getLogger(__name__)


class GitHubPlugin(BaseHttpPlugin[GitHubPluginConfig]):
    """GitHub integration plugin.

    Provides methods to interact with GitHub API (get PRs, post comments, etc.).
    Uses HttpService internally via BaseHttpPlugin.

    Supports two authentication modes:
    1. User OAuth tokens (for user identity, handled by Authlib)
    2. Installation access tokens (for repository access via GitHub App)
    """

    plugin_name = "github"
    config_class = GitHubPluginConfig
    priority = 20

    def __init__(self, plugin_config: GitHubPluginConfig):
        """Initialize GitHub plugin."""
        super().__init__(plugin_config)
        self._private_key: str | None = None

    async def startup(self) -> None:
        """Start HTTP service and load private key."""
        await super().startup()

        # Load GitHub App private key if configured
        if self.config.app and self.config.app.private_key_path:
            private_key_path = Path(self.config.app.private_key_path)
            # When running from a subdirectory (e.g., `make backend-run` does `cd backend/`),
            # relative paths from .env resolve against CWD, not the repo root.
            # Fall back to parent directory if the path doesn't exist at CWD.
            if not private_key_path.is_absolute() and not private_key_path.exists():
                parent_path = Path.cwd().parent / private_key_path
                if parent_path.exists():
                    private_key_path = parent_path

            if not private_key_path.exists():
                raise RuntimeError(
                    f"GitHub App private key not found at {private_key_path.resolve()}. "
                    f"Check GITHUB_APP_PRIVATE_KEY_PATH (current value: '{self.config.app.private_key_path}')."
                )

            self._private_key = private_key_path.read_text()
            logger.info(f"Loaded GitHub App private key from {private_key_path.resolve()}")

    def _get_base_url(self) -> str:
        """Get GitHub API base URL."""
        if self.config.app:
            return self.config.app.api_base_url
        return "https://api.github.com"

    def _get_default_headers(self) -> dict[str, str]:
        """Get default headers for GitHub API."""
        return {
            "Accept": "application/vnd.github.v3+json",
            # Note: Authorization header is added per-request based on auth type
        }

    # GitHub App Installation Authentication

    def _generate_jwt(self) -> str:
        """Generate a JWT for GitHub App authentication.

        Creates a short-lived JWT signed with the GitHub App's private key.
        This JWT is used to authenticate as the GitHub App itself.

        Returns:
            JWT token string

        Raises:
            HTTPException: If private key not loaded or JWT generation fails
        """
        if not self._private_key:
            raise HTTPException(
                status_code=500,
                detail="GitHub App private key not loaded. Check GITHUB_APP_PRIVATE_KEY_PATH configuration.",
            )

        if not self.config.app:
            raise HTTPException(status_code=500, detail="GitHub App configuration not found")

        # JWT expires in 10 minutes (GitHub maximum)
        now = int(time.time())
        expiration = now + (10 * 60)

        payload = {
            "iat": now,  # Issued at time
            "exp": expiration,  # Expiration time (10 minutes)
            "iss": self.config.app.app_id,  # Issuer (GitHub App ID)
        }

        try:
            # Sign JWT with RS256 algorithm using private key
            token = jwt.encode(payload, self._private_key, algorithm="RS256")
            return token
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to generate GitHub App JWT: {e}"
            ) from e

    async def get_installation_access_token(self, installation_id: str) -> str:
        """Get an installation access token for GitHub App.

        Uses the GitHub App JWT to request an installation access token,
        which grants access to repositories within the installation.

        Args:
            installation_id: GitHub App installation ID

        Returns:
            Installation access token string

        Raises:
            HTTPException: If token generation fails
        """
        # Generate JWT for GitHub App authentication
        jwt_token = self._generate_jwt()

        # Request installation access token
        url = f"/app/installations/{installation_id}/access_tokens"
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Accept": "application/vnd.github.v3+json",
        }

        try:
            response = await self.http.post(url, headers=headers)

            if response.status_code != 201:
                raise HTTPException(
                    status_code=response.status_code, detail=f"GitHub API error: {response.text}"
                )

            data = response.json()
            return data["token"]

        except HTTPException as e:
            raise e
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to get installation access token: {e}"
            ) from e

    async def delete_installation(self, installation_id: str) -> bool:
        """Delete a GitHub App installation.

        Args:
            installation_id: GitHub App installation ID

        Returns:
            True if deleted, False if not found (already gone)

        Raises:
            HTTPException: If GitHub API call fails
        """
        try:
            jwt_token = self._generate_jwt()
            headers = {
                "Authorization": f"Bearer {jwt_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }

            response = await self.http.delete(
                f"/app/installations/{installation_id}", headers=headers
            )

            if response.status_code == 204:
                logger.info(f"Successfully deleted installation {installation_id} from GitHub")
                return True
            if response.status_code == 404:
                logger.warning(
                    f"Installation {installation_id} not found on GitHub "
                    "(may have been deleted already)"
                )
                return False

            raise HTTPException(
                status_code=500,
                detail=f"Failed to delete installation from GitHub: {response.text}",
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error deleting installation {installation_id} from GitHub: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to delete installation from GitHub: {e!s}",
            ) from e

    async def verify_repo_access(self, installation_id: str, repo_path: str) -> None:
        """Verify the GitHub App installation has access to a repository.

        Args:
            installation_id: GitHub App installation ID
            repo_path: Repository path (e.g., "owner/repo")

        Raises:
            HTTPException: If repository not found or access denied
        """
        try:
            installation_token = await self.get_installation_access_token(installation_id)
        except HTTPException as e:
            raise HTTPException(
                status_code=500,
                detail="Failed to authenticate with GitHub. Check GitHub App configuration.",
            ) from e

        owner, repo = repo_path.split("/")
        headers = {
            "Authorization": f"token {installation_token}",
            "Accept": "application/vnd.github.v3+json",
        }

        response = await self.http.get(f"/repos/{owner}/{repo}", headers=headers)

        if response.status_code == 404:
            raise HTTPException(
                status_code=404,
                detail=f"Repository '{repo_path}' not found or the GitHub App does not have access to it.",
            )
        if response.status_code == 403:
            raise HTTPException(
                status_code=403,
                detail=f"GitHub App does not have permission to access repository '{repo_path}'.",
            )
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Failed to verify repository access: {response.text}",
            )

    async def verify_branch_exists(self, installation_id: str, repo_path: str, branch: str) -> None:
        """Verify a branch exists in a GitHub repository.

        Args:
            installation_id: GitHub App installation ID
            repo_path: Repository path (e.g., "owner/repo")
            branch: Branch name to verify

        Raises:
            HTTPException: If branch not found or access denied
        """
        try:
            installation_token = await self.get_installation_access_token(installation_id)
        except HTTPException as e:
            raise HTTPException(
                status_code=500,
                detail="Failed to authenticate with GitHub. Check GitHub App configuration.",
            ) from e

        owner, repo = repo_path.split("/")
        headers = {
            "Authorization": f"token {installation_token}",
            "Accept": "application/vnd.github.v3+json",
        }

        response = await self.http.get(f"/repos/{owner}/{repo}/branches/{branch}", headers=headers)

        if response.status_code == 404:
            raise HTTPException(
                status_code=404,
                detail=f"Branch '{branch}' not found in repository '{repo_path}'.",
            )
        if response.status_code not in (200, 301):
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Failed to verify branch: {response.text}",
            )

    async def fetch_installation_repositories(self, installation_token: str) -> list[dict]:
        """Fetch all repositories accessible by an installation.

        Args:
            installation_token: GitHub App installation access token

        Returns:
            List of repository objects

        Raises:
            HTTPException: If API call fails
        """
        headers = {
            "Authorization": f"token {installation_token}",
            "Accept": "application/vnd.github.v3+json",
        }

        try:
            response = await self.http.get("/installation/repositories", headers=headers)

            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code, detail=f"GitHub API error: {response.text}"
                )

            data = response.json()
            return data.get("repositories", [])

        except HTTPException as e:
            raise e
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to fetch installation repositories: {e}"
            ) from e

    # Public API methods (business logic)

    async def get_pull_request(
        self, owner: str, repo: str, pr_number: int, installation_token: str
    ):
        """Get pull request details from GitHub.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            installation_token: GitHub App installation access token

        Returns:
            Pull request data
        """
        headers = {"Authorization": f"token {installation_token}"}
        response = await self.http.get(f"/repos/{owner}/{repo}/pulls/{pr_number}", headers=headers)
        response.raise_for_status()
        return response.json()

    async def list_pull_requests(
        self, owner: str, repo: str, installation_token: str, state: str = "open"
    ):
        """List pull requests for a repository with pagination.

        Fetches all pull requests by following pagination links.
        GitHub returns max 100 items per page.

        Args:
            owner: Repository owner
            repo: Repository name
            installation_token: GitHub App installation access token
            state: PR state (open, closed, all)

        Returns:
            List of all pull requests
        """
        headers = {"Authorization": f"token {installation_token}"}
        all_prs = []
        page = 1
        per_page = 100  # Max allowed by GitHub

        while True:
            response = await self.http.get(
                f"/repos/{owner}/{repo}/pulls",
                headers=headers,
                params={"state": state, "page": page, "per_page": per_page},
            )
            response.raise_for_status()
            prs = response.json()

            if not prs:  # No more results
                break

            all_prs.extend(prs)

            # If we got fewer than per_page, we're on the last page
            if len(prs) < per_page:
                break

            page += 1

        logger.info(f"Fetched {len(all_prs)} total PRs for {owner}/{repo} (state={state})")
        return all_prs

    async def post_comment(self, owner: str, repo: str, pr_number: int, body: str):
        """Post a comment on a pull request.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            body: Comment text

        Returns:
            Comment data
        """
        response = await self.http.post(
            f"/repos/{owner}/{repo}/issues/{pr_number}/comments",
            json={"body": body},
        )
        response.raise_for_status()
        return response.json()

    # User identity methods (for OAuth login)

    async def fetch_user_info(self, access_token: str) -> dict:
        """Fetch the authenticated user's profile from GitHub.

        Args:
            access_token: User's OAuth access token

        Returns:
            User profile dict with id, login, email, avatar_url, etc.
        """
        headers = {"Authorization": f"Bearer {access_token}"}
        response = await self.http.get("/user", headers=headers)
        response.raise_for_status()
        return response.json()

    async def fetch_user_emails(self, access_token: str) -> list[dict]:
        """Fetch the authenticated user's email addresses from GitHub.

        Args:
            access_token: User's OAuth access token

        Returns:
            List of email objects with email, primary, verified fields.
        """
        headers = {"Authorization": f"Bearer {access_token}"}
        response = await self.http.get("/user/emails", headers=headers)
        if response.status_code != 200:
            return []
        return response.json()

    # User Organization methods (for OAuth login sync)

    async def fetch_user_organizations(self, username: str) -> list[dict]:
        """Fetch all PUBLIC organizations the user is a member of.

        Uses the public endpoint /users/{username}/orgs which doesn't require
        authentication and returns public org memberships.

        Args:
            username: GitHub username

        Returns:
            List of organization objects from GitHub API

        Raises:
            HTTPException: If API call fails
        """
        headers = {
            "Accept": "application/vnd.github.v3+json",
        }

        orgs = []
        page = 1
        per_page = 100

        while True:
            response = await self.http.get(
                f"/users/{username}/orgs",
                headers=headers,
                params={"page": page, "per_page": per_page},
            )

            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"GitHub API error: {response.text}",
                )

            page_orgs = response.json()
            if not page_orgs:
                break

            orgs.extend(page_orgs)

            if len(page_orgs) < per_page:
                break

            page += 1

        return orgs

    async def get_user_org_membership(self, access_token: str, org_login: str) -> str:
        """Get the user's membership role in a GitHub organization.

        Args:
            access_token: User's OAuth access token
            org_login: Organization login name (e.g., "my-org")

        Returns:
            User role: "admin" or "member"

        Raises:
            HTTPException: If API call fails or user is not a member
        """
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github.v3+json",
        }

        response = await self.http.get(
            f"/user/memberships/orgs/{org_login}",
            headers=headers,
        )

        if response.status_code == 404:
            # User is not a member of this org
            return "member"  # Default to member if not found

        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"GitHub API error: {response.text}",
            )

        data = response.json()
        # GitHub returns "admin" or "member" in the role field
        return data.get("role", "member")

    async def fetch_user_installations(self, access_token: str) -> list[dict]:
        """Fetch all GitHub App installations the user has access to.

        This uses the /user/installations endpoint which returns installations
        where the user has explicit permission (read, write, or admin).
        This works because the user is a member of the organizations where
        the app is installed.

        Args:
            access_token: User's OAuth access token from GitHub App login

        Returns:
            List of installation objects with account info (org/user details)

        Raises:
            HTTPException: If API call fails
        """
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github.v3+json",
        }

        installations = []
        page = 1
        per_page = 100

        while True:
            response = await self.http.get(
                "/user/installations",
                headers=headers,
                params={"page": page, "per_page": per_page},
            )

            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"GitHub API error: {response.text}",
                )

            data = response.json()
            page_installations = data.get("installations", [])

            if not page_installations:
                break

            installations.extend(page_installations)

            # Check if we've received all installations
            total_count = data.get("total_count", 0)
            if len(installations) >= total_count:
                break

            page += 1

        return installations

    # Organization Member methods

    async def fetch_organization_members(
        self, installation_token: str, org_name: str
    ) -> list[dict]:
        """Fetch all members of a GitHub organization.

        Uses GET /orgs/{org}/members endpoint with pagination.
        Requires the installation token to have read:org permission.

        Args:
            installation_token: GitHub App installation access token
            org_name: Organization login name

        Returns:
            List of member objects with id, login, avatar_url

        Raises:
            HTTPException: If API call fails
        """
        headers = {
            "Authorization": f"token {installation_token}",
            "Accept": "application/vnd.github.v3+json",
        }

        members = []
        page = 1
        per_page = 100

        while True:
            try:
                response = await self.http.get(
                    f"/orgs/{org_name}/members",
                    headers=headers,
                    params={"page": page, "per_page": per_page},
                )

                if response.status_code == 403:
                    # May not have permission to list members
                    logger.warning(
                        f"No permission to list members for org {org_name}. "
                        "Ensure the GitHub App has 'members' read permission."
                    )
                    return []

                if response.status_code != 200:
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"GitHub API error: {response.text}",
                    )

                page_members = response.json()
                if not page_members:
                    break

                members.extend(page_members)

                if len(page_members) < per_page:
                    break

                page += 1

            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Failed to fetch org members: {e}")
                raise HTTPException(
                    status_code=500, detail=f"Failed to fetch organization members: {e}"
                ) from e

        logger.info(f"Fetched {len(members)} members for org {org_name}")
        return members

    async def get_organization_member_role(
        self, installation_token: str, org_name: str, username: str
    ) -> str:
        """Get a member's role in an organization.

        Uses the /orgs/{org}/memberships/{username} endpoint.

        Args:
            installation_token: GitHub App installation access token
            org_name: Organization login name
            username: GitHub username

        Returns:
            Role string: "admin" or "member"
        """
        headers = {
            "Authorization": f"token {installation_token}",
            "Accept": "application/vnd.github.v3+json",
        }

        try:
            response = await self.http.get(
                f"/orgs/{org_name}/memberships/{username}",
                headers=headers,
            )

            if response.status_code == 404:
                return "member"  # Not found, assume member

            if response.status_code != 200:
                logger.warning(f"Failed to get role for {username} in {org_name}: {response.text}")
                return "member"  # Default to member on error

            data = response.json()
            return data.get("role", "member")

        except Exception as e:
            logger.warning(f"Error getting role for {username}: {e}")
            return "member"

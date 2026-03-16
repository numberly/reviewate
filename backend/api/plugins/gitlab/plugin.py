"""GitLab integration plugin.

Provides GitLab API functionality using BaseHttpPlugin.
"""

import logging
from urllib.parse import quote

from fastapi import HTTPException

from api.plugins.gitlab.config import GitLabPluginConfig
from api.plugins.gitlab.schemas import GitlabTokenType
from api.plugins.httpx.client import BaseHttpPlugin

logger = logging.getLogger(__name__)


class GitLabPlugin(BaseHttpPlugin[GitLabPluginConfig]):
    """GitLab integration plugin.

    Provides methods to interact with GitLab API (get MRs, post comments, etc.).
    Uses HttpService internally via BaseHttpPlugin.
    """

    plugin_name = "gitlab"
    config_class = GitLabPluginConfig
    priority = 20

    def _get_base_url(self) -> str:
        """Get GitLab API base URL."""
        if self.config.oauth:
            instance_url = self.config.oauth.instance_url
            return f"{instance_url}/api/v4"
        return "https://gitlab.com/api/v4"

    def _get_default_headers(self) -> dict[str, str]:
        """Get default headers for GitLab API."""
        return {}

    def _get_instance_url(self) -> str:
        """Get GitLab instance URL (without /api/v4 suffix)."""
        if self.config.oauth:
            return self.config.oauth.instance_url
        return "https://gitlab.com"

    async def verify_repo_access(
        self, access_token: str, provider_url: str, repo_path: str
    ) -> None:
        """Verify the GitLab token has access to a repository.

        Args:
            access_token: Decrypted GitLab access token
            provider_url: GitLab instance URL (e.g., "https://gitlab.com")
            repo_path: Repository path (e.g., "owner/repo")

        Raises:
            HTTPException: If repository not found or access denied
        """
        encoded_path = quote(repo_path, safe="")
        response = await self.http.get(
            f"{provider_url}/api/v4/projects/{encoded_path}",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        if response.status_code == 404:
            raise HTTPException(
                status_code=404,
                detail=f"Repository '{repo_path}' not found or the token does not have access to it.",
            )
        if response.status_code in (401, 403):
            raise HTTPException(
                status_code=403,
                detail=f"GitLab token does not have permission to access repository '{repo_path}'.",
            )
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Failed to verify repository access: {response.text}",
            )

    async def verify_branch_exists(
        self, access_token: str, provider_url: str, repo_path: str, branch: str
    ) -> None:
        """Verify a branch exists in a GitLab repository.

        Args:
            access_token: Decrypted GitLab access token
            provider_url: GitLab instance URL (e.g., "https://gitlab.com")
            repo_path: Repository path (e.g., "owner/repo")
            branch: Branch name to verify

        Raises:
            HTTPException: If branch not found or access denied
        """
        encoded_path = quote(repo_path, safe="")
        encoded_branch = quote(branch, safe="")
        response = await self.http.get(
            f"{provider_url}/api/v4/projects/{encoded_path}/repository/branches/{encoded_branch}",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        if response.status_code == 404:
            raise HTTPException(
                status_code=404,
                detail=f"Branch '{branch}' not found in repository '{repo_path}'.",
            )
        if response.status_code not in (200,):
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Failed to verify branch: {response.text}",
            )

    # Token verification and management methods

    async def verify_token(self, access_token: str, provider_url: str | None = None) -> dict:
        """Verify GitLab access token and get user information.

        Uses /api/v4/user endpoint to verify the token and determine its type.

        Args:
            access_token: GitLab token (group, project, or personal)
            provider_url: Optional GitLab instance URL (defaults to config)

        Returns:
            User information including:
                - id: User ID
                - username: Username (contains prefix for bot tokens)
                - bot: Boolean indicating if it's a bot token
                - name: Display name
                - email: Email address
                - ... (other user fields)

        Raises:
            HTTPException: If token is invalid or API call fails
        """
        base_url = provider_url or self._get_instance_url()
        response = await self.http.get(
            f"{base_url}/api/v4/user",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        if response.status_code == 401:
            raise HTTPException(
                status_code=401,
                detail="Invalid GitLab access token",
            )

        if response.status_code != 200:
            raise HTTPException(
                status_code=500,
                detail=f"GitLab API returned {response.status_code}: {response.text}",
            )

        return response.json()

    def get_token_type(self, user_data: dict) -> GitlabTokenType | None:
        """Determine the type of token from user data.

        Args:
            user_data: User data from /api/v4/user endpoint

        Returns:
            Token type: GROUP_ACCESS_TOKEN, PROJECT_ACCESS_TOKEN, PERSONAL_ACCESS_TOKEN, or None
        """
        is_bot = user_data.get("bot", False)
        username = user_data.get("username", "")

        if not is_bot:
            return GitlabTokenType.PERSONAL_ACCESS_TOKEN

        if username.startswith("group_") and "_bot_" in username:
            return GitlabTokenType.GROUP_ACCESS_TOKEN

        if username.startswith("project_") and "_bot_" in username:
            return GitlabTokenType.PROJECT_ACCESS_TOKEN

        return None

    # Group-related methods

    async def fetch_group(self, access_token: str, group_id: str) -> dict:
        """Fetch GitLab group information.

        Args:
            access_token: GitLab access token
            group_id: Group ID

        Returns:
            Group information

        Raises:
            HTTPException: If API call fails
        """
        instance_url = self._get_instance_url()
        response = await self.http.get(
            f"{instance_url}/api/v4/groups/{group_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=500,
                detail=f"GitLab API returned {response.status_code}: {response.text}",
            )

        return response.json()

    async def resolve_root_group(self, access_token: str, group_id: str) -> dict:
        """Walk up the group hierarchy to find the root (top-level) group.

        Follows parent_id chain until reaching a group with no parent.
        Stops early on 403/404 if the token can't read a parent group.

        Args:
            access_token: GitLab access token
            group_id: Starting group ID

        Returns:
            Root group info dict (or highest accessible group on 403)
        """
        current = await self.fetch_group(access_token, group_id)
        while current.get("parent_id") is not None:
            parent_id = str(current["parent_id"])
            try:
                parent = await self.fetch_group(access_token, parent_id)
                current = parent
            except HTTPException:
                break  # Can't access parent, use current as root
        return current

    async def fetch_group_projects(self, access_token: str, group_id: str) -> list[dict]:
        """Fetch all projects in a GitLab group.

        Args:
            access_token: GitLab access token
            group_id: Group ID

        Returns:
            List of project information

        Raises:
            HTTPException: If API call fails
        """
        instance_url = self._get_instance_url()
        projects = []
        page = 1
        per_page = 100  # Max per page

        while True:
            response = await self.http.get(
                f"{instance_url}/api/v4/groups/{group_id}/projects",
                headers={"Authorization": f"Bearer {access_token}"},
                params={
                    "page": page,
                    "per_page": per_page,
                    "include_subgroups": True,
                    "with_shared": False,
                },
            )

            if response.status_code != 200:
                raise HTTPException(
                    status_code=500,
                    detail=f"GitLab API returned {response.status_code}: {response.text}",
                )

            page_projects = response.json()
            if not page_projects:
                break

            projects.extend(page_projects)
            page += 1

        return projects

    async def determine_user_role_in_group(
        self,
        access_token: str,
        group_id: str,
        gitlab_user_id: str | None = None,
        user_email: str | None = None,
    ) -> str:
        """Determine user's role in a GitLab group.

        Args:
            access_token: GitLab access token (can be bot token or user token)
            group_id: Group ID
            gitlab_user_id: GitLab user ID (preferred - enables direct lookup)
            user_email: User's email address (fallback if gitlab_user_id not available)

        Returns:
            User role: "admin", "member", or "guest"

        Raises:
            HTTPException: If API call fails
        """
        instance_url = self._get_instance_url()

        # If we have the user's GitLab ID, use direct member lookup (more efficient)
        if gitlab_user_id:
            response = await self.http.get(
                f"{instance_url}/api/v4/groups/{group_id}/members/all/{gitlab_user_id}",
                headers={"Authorization": f"Bearer {access_token}"},
            )

            if response.status_code == 200:
                member = response.json()
                access_level = member.get("access_level", 0)
                # GitLab access levels: 10=Guest, 20=Reporter, 30=Developer, 40=Maintainer, 50=Owner
                if access_level >= 40:
                    return "admin"
                elif access_level >= 30:
                    return "member"
                else:
                    return "guest"
            elif response.status_code == 404:
                # User is not a member of this group
                return "guest"

        # Fallback: list all members and match by email
        if user_email:
            response = await self.http.get(
                f"{instance_url}/api/v4/groups/{group_id}/members/all",
                headers={"Authorization": f"Bearer {access_token}"},
            )

            if response.status_code != 200:
                raise HTTPException(
                    status_code=500,
                    detail=f"GitLab API returned {response.status_code}: {response.text}",
                )

            members = response.json()
            for member in members:
                if member.get("email") == user_email:
                    access_level = member.get("access_level", 0)
                    if access_level >= 40:
                        return "admin"
                    elif access_level >= 30:
                        return "member"

        return "guest"

    async def fetch_group_members(self, access_token: str, group_id: str) -> list[dict]:
        """Fetch all members of a GitLab group with pagination.

        Uses GET /groups/{id}/members endpoint.

        Args:
            access_token: GitLab access token (group, project, or personal)
            group_id: Group ID

        Returns:
            List of member objects with id, username, avatar_url, access_level

        Raises:
            HTTPException: If API call fails
        """
        instance_url = self._get_instance_url()
        members = []
        page = 1
        per_page = 100

        while True:
            try:
                response = await self.http.get(
                    f"{instance_url}/api/v4/groups/{group_id}/members/all",
                    headers={"Authorization": f"Bearer {access_token}"},
                    params={"page": page, "per_page": per_page},
                )

                if response.status_code == 403:
                    logger.warning(
                        f"No permission to list members for group {group_id}. "
                        "Ensure the token has 'read_api' scope."
                    )
                    return []

                if response.status_code != 200:
                    raise HTTPException(
                        status_code=500,
                        detail=f"GitLab API returned {response.status_code}: {response.text}",
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
                logger.error(f"Failed to fetch group members: {e}")
                raise HTTPException(
                    status_code=500, detail=f"Failed to fetch group members: {e}"
                ) from e

        logger.info(f"Fetched {len(members)} members for group {group_id}")
        return members

    def map_access_level_to_role(self, access_level: int) -> str:
        """Map GitLab access level to Reviewate role.

        GitLab access levels:
        - 10 = Guest
        - 20 = Reporter
        - 30 = Developer
        - 40 = Maintainer
        - 50 = Owner

        Args:
            access_level: GitLab access level integer

        Returns:
            Role string: "admin" for Maintainer/Owner, "member" otherwise
        """
        if access_level >= 40:
            return "admin"
        return "member"

    # Project-related methods

    async def fetch_project(self, access_token: str, project_id: str) -> dict:
        """Fetch GitLab project information.

        Args:
            access_token: GitLab access token
            project_id: Project ID

        Returns:
            Project information

        Raises:
            HTTPException: If API call fails
        """
        instance_url = self._get_instance_url()
        response = await self.http.get(
            f"{instance_url}/api/v4/projects/{project_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=500,
                detail=f"GitLab API returned {response.status_code}: {response.text}",
            )

        return response.json()

    async def determine_user_role_in_project(
        self,
        access_token: str,
        project_id: str,
        gitlab_user_id: str | None = None,
        user_email: str | None = None,
    ) -> str:
        """Determine user's role in a GitLab project.

        Args:
            access_token: GitLab access token (can be bot token or user token)
            project_id: Project ID
            gitlab_user_id: GitLab user ID (preferred - enables direct lookup)
            user_email: User's email address (fallback if gitlab_user_id not available)

        Returns:
            User role: "admin", "member", or "guest"

        Raises:
            HTTPException: If API call fails
        """
        instance_url = self._get_instance_url()

        # If we have the user's GitLab ID, use direct member lookup (more efficient)
        if gitlab_user_id:
            response = await self.http.get(
                f"{instance_url}/api/v4/projects/{project_id}/members/all/{gitlab_user_id}",
                headers={"Authorization": f"Bearer {access_token}"},
            )

            if response.status_code == 200:
                member = response.json()
                access_level = member.get("access_level", 0)
                # GitLab access levels: 10=Guest, 20=Reporter, 30=Developer, 40=Maintainer, 50=Owner
                if access_level >= 40:
                    return "admin"
                elif access_level >= 30:
                    return "member"
                else:
                    return "guest"
            elif response.status_code == 404:
                # User is not a member of this project
                return "guest"

        # Fallback: list all members and match by email
        if user_email:
            response = await self.http.get(
                f"{instance_url}/api/v4/projects/{project_id}/members/all",
                headers={"Authorization": f"Bearer {access_token}"},
            )

            if response.status_code != 200:
                raise HTTPException(
                    status_code=500,
                    detail=f"GitLab API returned {response.status_code}: {response.text}",
                )

            members = response.json()
            for member in members:
                if member.get("email") == user_email:
                    access_level = member.get("access_level", 0)
                    # GitLab access levels: 10=Guest, 20=Reporter, 30=Developer, 40=Maintainer, 50=Owner
                    if access_level >= 40:
                        return "admin"
                    elif access_level >= 30:
                        return "member"

        return "guest"

    async def fetch_user_groups(self, access_token: str) -> list[dict]:
        """Fetch all groups the user is a member of using their OAuth token.

        Args:
            access_token: User's OAuth access token

        Returns:
            List of group objects from GitLab API

        Raises:
            HTTPException: If API call fails
        """
        instance_url = self._get_instance_url()
        groups = []
        page = 1
        per_page = 100

        while True:
            response = await self.http.get(
                f"{instance_url}/api/v4/groups",
                headers={"Authorization": f"Bearer {access_token}"},
                params={
                    "page": page,
                    "per_page": per_page,
                    "min_access_level": 10,  # Guest level and above
                },
            )

            if response.status_code != 200:
                raise HTTPException(
                    status_code=500,
                    detail=f"GitLab API returned {response.status_code}: {response.text}",
                )

            page_groups = response.json()

            if not page_groups:
                break

            groups.extend(page_groups)

            # Check if there are more pages
            if len(page_groups) < per_page:
                break

            page += 1

        return groups

    async def fetch_user_namespaces(self, access_token: str) -> list[dict]:
        """Fetch namespaces owned by the user (includes personal namespace).

        Args:
            access_token: User's OAuth access token

        Returns:
            List of namespace objects from GitLab API

        Raises:
            HTTPException: If API call fails
        """
        instance_url = self._get_instance_url()

        response = await self.http.get(
            f"{instance_url}/api/v4/namespaces",
            headers={"Authorization": f"Bearer {access_token}"},
            params={
                "owned_only": "true",
            },
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=500,
                detail=f"GitLab API returned {response.status_code}: {response.text}",
            )

        return response.json()

    # Public API methods (MR business logic)

    async def get_merge_request(self, project_id: str, mr_iid: int) -> dict:
        """Get merge request details from GitLab.

        Args:
            project_id: Project ID or path
            mr_iid: Merge request IID

        Returns:
            Merge request data
        """
        response = await self.http.get(f"/projects/{project_id}/merge_requests/{mr_iid}")
        response.raise_for_status()
        return response.json()

    async def list_merge_requests(
        self, project_id: str, state: str = "opened", access_token: str | None = None
    ) -> list[dict]:
        """List merge requests for a project with pagination.

        Fetches all merge requests by following pagination.
        GitLab returns max 100 items per page.

        Args:
            project_id: Project ID or path
            state: MR state (opened, closed, merged, all)
            access_token: Optional access token. When provided, uses absolute URL
                with Bearer auth instead of the default base URL.

        Returns:
            List of all merge requests
        """
        all_mrs = []
        page = 1
        per_page = 100  # Max allowed by GitLab

        # When access_token is provided, use absolute URL with instance base
        headers = {}
        if access_token:
            instance_url = self._get_instance_url()
            url = f"{instance_url}/api/v4/projects/{project_id}/merge_requests"
            headers["Authorization"] = f"Bearer {access_token}"
        else:
            url = f"/projects/{project_id}/merge_requests"

        while True:
            response = await self.http.get(
                url,
                headers=headers or None,
                params={"state": state, "page": page, "per_page": per_page},
            )
            response.raise_for_status()
            mrs = response.json()

            if not mrs:  # No more results
                break

            all_mrs.extend(mrs)

            # If we got fewer than per_page, we're on the last page
            if len(mrs) < per_page:
                break

            page += 1

        return all_mrs

    async def post_comment(self, project_id: str, mr_iid: int, body: str) -> dict:
        """Post a comment on a merge request.

        Args:
            project_id: Project ID or path
            mr_iid: Merge request IID
            body: Comment text

        Returns:
            Comment data
        """
        response = await self.http.post(
            f"/projects/{project_id}/merge_requests/{mr_iid}/notes",
            json={"body": body},
        )
        response.raise_for_status()
        return response.json()

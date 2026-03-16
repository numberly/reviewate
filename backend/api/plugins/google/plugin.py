"""Google OAuth integration plugin.

Provides Google OAuth functionality using BaseHttpPlugin.
"""

from api.plugins.google.config import GooglePluginConfig
from api.plugins.httpx.client import BaseHttpPlugin


class GooglePlugin(BaseHttpPlugin[GooglePluginConfig]):
    """Google OAuth plugin.

    Provides methods to interact with Google OAuth APIs.
    Uses HttpService internally via BaseHttpPlugin.
    """

    plugin_name = "google"
    config_class = GooglePluginConfig
    priority = 20

    def _get_base_url(self) -> str:
        """Get Google OAuth userinfo URL."""
        if self.config.oauth:
            return self.config.oauth.userinfo_url
        return "https://www.googleapis.com/oauth2/v3/userinfo"

    def _get_default_headers(self) -> dict[str, str]:
        """Get default headers for Google API."""
        return {}

    # Public API methods (business logic)

    async def get_user_info(self, access_token: str):
        """Get user info from Google.

        Args:
            access_token: OAuth access token

        Returns:
            User info data
        """
        response = await self.http.get(
            "/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        return response.json()

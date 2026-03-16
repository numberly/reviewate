"""Constants used across the API."""


class GitLabAccessLevel:
    """GitLab access levels for groups and projects.

    See: https://docs.gitlab.com/ee/api/members.html#valid-access-levels
    """

    OWNER = 50
    MAINTAINER = 40
    DEVELOPER = 30
    REPORTER = 20
    GUEST = 10

    @classmethod
    def is_admin_level(cls, access_level: int) -> bool:
        """Check if access level qualifies for admin role.

        Args:
            access_level: GitLab access level integer

        Returns:
            True if Owner or Maintainer level
        """
        return access_level >= cls.MAINTAINER

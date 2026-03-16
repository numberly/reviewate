"""Polyfactory factories for generating test data."""

from datetime import UTC, datetime
from uuid import uuid4

from polyfactory.factories.pydantic_factory import ModelFactory
from polyfactory.factories.sqlalchemy_factory import SQLAlchemyFactory

from api.models import (
    Execution,
    Organization,
    OrganizationMembership,
    ProviderIdentity,
    PullRequest,
    Repository,
    User,
)
from api.routers.organizations.schemas import OrganizationEventMessage
from api.routers.pull_requests.schemas import PullRequestEventMessage
from api.routers.queue.schemas import ExecutionStatusMessage, ReviewJobMessage
from api.routers.repositories.schemas import RepositoryEventMessage
from api.routers.sources.gitlab.schemas import (
    GitLabSyncGroupMessage,
    GitLabSyncRepositoryMRsMessage,
)
from api.routers.webhooks.github.schemas import (
    GitHubSyncInstallationMessage,
    GitHubSyncRepositoryPRsMessage,
)


class UserFactory(SQLAlchemyFactory[User]):
    """Factory for creating User instances with realistic fake data."""

    __model__ = User
    __set_relationships__ = False
    __check_model__ = False

    @classmethod
    def id(cls) -> str:
        """Generate a unique UUID for user ID."""
        return uuid4()

    @classmethod
    def email(cls) -> str | None:
        """Generate a unique email address."""
        return cls.__faker__.unique.email()

    @classmethod
    def created_at(cls) -> datetime:
        """Generate creation timestamp."""
        return datetime.now(UTC)

    @classmethod
    def updated_at(cls) -> datetime:
        """Generate update timestamp."""
        return datetime.now(UTC)


class ProviderIdentityFactory(SQLAlchemyFactory[ProviderIdentity]):
    """Factory for creating ProviderIdentity instances."""

    __model__ = ProviderIdentity
    __set_relationships__ = False
    __check_model__ = False

    @classmethod
    def id(cls) -> str:
        """Generate a unique UUID for identity ID."""
        return uuid4()

    @classmethod
    def provider(cls) -> str:
        """Generate provider type."""
        return cls.__faker__.random_element(elements=("github", "gitlab", "google"))

    @classmethod
    def external_id(cls) -> str:
        """Generate external user ID."""
        return str(cls.__faker__.random_int(min=100000, max=999999))

    @classmethod
    def username(cls) -> str | None:
        """Generate username."""
        return cls.__faker__.user_name()

    @classmethod
    def avatar_url(cls) -> str | None:
        """Generate avatar URL."""
        return f"https://avatars.githubusercontent.com/u/{cls.__faker__.random_int(min=1000, max=99999)}"

    @classmethod
    def user_id(cls) -> str | None:
        """Generate linked user ID (None by default - unlinked)."""
        return None

    @classmethod
    def created_at(cls) -> datetime:
        """Generate creation timestamp."""
        return datetime.now(UTC)

    @classmethod
    def updated_at(cls) -> datetime:
        """Generate update timestamp."""
        return datetime.now(UTC)


class OrganizationFactory(SQLAlchemyFactory[Organization]):
    """Factory for creating Organization instances with realistic fake data."""

    __model__ = Organization
    __set_relationships__ = False
    __check_model__ = False

    @classmethod
    def id(cls) -> str:
        """Generate a unique UUID for organization ID."""
        return uuid4()

    @classmethod
    def name(cls) -> str:
        """Generate organization name."""
        return cls.__faker__.company()

    @classmethod
    def external_org_id(cls) -> str:
        """Generate external organization ID (simulating GitHub/GitLab org ID)."""
        return str(cls.__faker__.random_int(min=100000, max=999999))

    @classmethod
    def installation_id(cls) -> str:
        """Generate app installation ID."""
        return str(cls.__faker__.random_int(min=100000, max=999999))

    @classmethod
    def provider(cls) -> str:
        """Generate provider (github or gitlab)."""
        return cls.__faker__.random_element(elements=("github", "gitlab"))

    @classmethod
    def provider_url(cls) -> str:
        """Generate provider URL."""
        return cls.__faker__.random_element(elements=("https://github.com", "https://gitlab.com"))

    @classmethod
    def guidelines(cls) -> str | None:
        """Return default guidelines (None)."""
        return None

    @classmethod
    def automatic_review_trigger(cls) -> str:
        """Return default automatic review trigger (none)."""
        return "none"

    @classmethod
    def automatic_summary_trigger(cls) -> str:
        """Return default automatic summary trigger (never)."""
        return "never"

    @classmethod
    def created_at(cls) -> datetime:
        """Generate creation timestamp."""
        return datetime.now(UTC)

    @classmethod
    def updated_at(cls) -> datetime:
        """Generate update timestamp."""
        return datetime.now(UTC)


class OrganizationMembershipFactory(SQLAlchemyFactory[OrganizationMembership]):
    """Factory for creating OrganizationMembership instances."""

    __model__ = OrganizationMembership
    __set_relationships__ = False
    __check_model__ = False

    @classmethod
    def id(cls) -> str:
        """Generate membership ID."""
        return uuid4()

    @classmethod
    def provider_identity_id(cls) -> str:
        """Generate provider identity ID."""
        return uuid4()

    @classmethod
    def organization_id(cls) -> str:
        """Generate organization ID."""
        return uuid4()

    @classmethod
    def role(cls) -> str:
        """Generate role (admin or member)."""
        return cls.__faker__.random_element(elements=("admin", "member"))

    @classmethod
    def reviewate_enabled(cls) -> bool:
        """Generate reviewate enabled (default True)."""
        return True

    @classmethod
    def created_at(cls) -> datetime:
        """Generate creation timestamp."""
        return datetime.now(UTC)

    @classmethod
    def updated_at(cls) -> datetime:
        """Generate update timestamp."""
        return datetime.now(UTC)


class RepositoryFactory(SQLAlchemyFactory[Repository]):
    """Factory for creating Repository instances with realistic fake data."""

    __model__ = Repository
    __set_relationships__ = False
    __check_model__ = False

    @classmethod
    def id(cls) -> str:
        """Generate a unique UUID for repository ID."""
        return uuid4()

    @classmethod
    def organization_id(cls) -> str:
        """Generate organization ID."""
        return uuid4()

    @classmethod
    def external_repo_id(cls) -> str:
        """Generate external repository ID (simulating GitHub/GitLab repo ID)."""
        return str(cls.__faker__.random_int(min=100000, max=999999))

    @classmethod
    def platform(cls) -> str:
        """Generate platform (github or gitlab)."""
        return cls.__faker__.random_element(elements=("github", "gitlab"))

    @classmethod
    def name(cls) -> str:
        """Generate repository name."""
        # Generate a slug-like name (e.g., "my-project-name")
        words = cls.__faker__.words(nb=2)
        return "-".join(words)

    @classmethod
    def web_url(cls) -> str:
        """Generate repository web URL."""
        platform = cls.__faker__.random_element(elements=("github", "gitlab"))
        org = cls.__faker__.user_name()
        repo = "-".join(cls.__faker__.words(nb=2))
        if platform == "github":
            return f"https://github.com/{org}/{repo}"
        else:
            return f"https://gitlab.com/{org}/{repo}"

    @classmethod
    def provider(cls) -> str:
        """Generate provider (github or gitlab)."""
        return cls.__faker__.random_element(elements=("github", "gitlab"))

    @classmethod
    def provider_url(cls) -> str:
        """Generate provider URL."""
        return cls.__faker__.random_element(elements=("https://github.com", "https://gitlab.com"))

    @classmethod
    def guidelines(cls) -> str | None:
        """Return default guidelines (None - inherits from org)."""
        return None

    @classmethod
    def automatic_review_trigger(cls) -> str | None:
        """Return default automatic review trigger (None - inherits from org)."""
        return None

    @classmethod
    def automatic_summary_trigger(cls) -> str | None:
        """Return default automatic summary trigger (None - inherits from org)."""
        return None

    @classmethod
    def created_at(cls) -> datetime:
        """Generate creation timestamp."""
        return datetime.now(UTC)

    @classmethod
    def updated_at(cls) -> datetime:
        """Generate update timestamp."""
        return datetime.now(UTC)


class ExecutionFactory(SQLAlchemyFactory[Execution]):
    """Factory for creating Execution instances with realistic fake data."""

    __model__ = Execution
    __set_relationships__ = False
    __check_model__ = False

    @classmethod
    def id(cls) -> str:
        """Generate a unique UUID for execution ID."""
        return uuid4()

    @classmethod
    def organization_id(cls) -> str:
        """Generate organization ID."""
        return uuid4()

    @classmethod
    def repository_id(cls) -> str:
        """Generate repository ID."""
        return uuid4()

    @classmethod
    def pr_number(cls) -> int:
        """Generate PR number."""
        return cls.__faker__.random_int(min=1, max=9999)

    @classmethod
    def commit_sha(cls) -> str:
        """Generate commit SHA (40 character hex string)."""
        return cls.__faker__.sha1()

    @classmethod
    def status(cls) -> str:
        """Generate execution status."""
        return cls.__faker__.random_element(elements=("pending", "running", "success", "failed"))

    @classmethod
    def created_at(cls) -> datetime:
        """Generate creation timestamp."""
        return datetime.now(UTC)

    @classmethod
    def updated_at(cls) -> datetime:
        """Generate update timestamp."""
        return datetime.now(UTC)


class PullRequestFactory(SQLAlchemyFactory[PullRequest]):
    """Factory for creating PullRequest instances with realistic fake data."""

    __model__ = PullRequest
    __set_relationships__ = False
    __check_model__ = False

    @classmethod
    def id(cls) -> str:
        """Generate a unique UUID for pull request ID."""
        return uuid4()

    @classmethod
    def organization_id(cls) -> str:
        """Generate organization ID."""
        return uuid4()

    @classmethod
    def repository_id(cls) -> str:
        """Generate repository ID."""
        return uuid4()

    @classmethod
    def pr_number(cls) -> int:
        """Generate PR number."""
        return cls.__faker__.random_int(min=1, max=9999)

    @classmethod
    def external_pr_id(cls) -> str:
        """Generate external PR ID (simulating GitHub/GitLab PR ID)."""
        return str(cls.__faker__.random_int(min=100000, max=999999))

    @classmethod
    def title(cls) -> str:
        """Generate PR title."""
        return cls.__faker__.sentence(nb_words=6)

    @classmethod
    def author(cls) -> str:
        """Generate PR author username."""
        return cls.__faker__.user_name()

    @classmethod
    def state(cls) -> str:
        """Generate PR state (open, closed, merged)."""
        return cls.__faker__.random_element(elements=("open", "closed", "merged"))

    @classmethod
    def head_branch(cls) -> str:
        """Generate source branch name."""
        return f"feature/{cls.__faker__.word()}"

    @classmethod
    def base_branch(cls) -> str:
        """Generate target branch name."""
        return "main"

    @classmethod
    def head_sha(cls) -> str:
        """Generate head commit SHA (40 character hex string)."""
        return cls.__faker__.sha1()

    @classmethod
    def pr_url(cls) -> str:
        """Generate PR URL."""
        org = cls.__faker__.user_name()
        repo = "-".join(cls.__faker__.words(nb=2))
        pr_num = cls.__faker__.random_int(min=1, max=999)
        return f"https://github.com/{org}/{repo}/pull/{pr_num}"

    @classmethod
    def created_at(cls) -> datetime:
        """Generate creation timestamp."""
        return datetime.now(UTC)

    @classmethod
    def updated_at(cls) -> datetime:
        """Generate update timestamp."""
        return datetime.now(UTC)


class ReviewJobMessageFactory(ModelFactory[ReviewJobMessage]):
    """Factory for creating ReviewJobMessage instances with realistic fake data."""

    __model__ = ReviewJobMessage
    __check_model__ = False

    @classmethod
    def job_id(cls) -> str:
        """Generate a unique UUID for job ID."""
        return str(uuid4())

    @classmethod
    def organization_id(cls) -> str:
        """Generate organization ID."""
        return str(uuid4())

    @classmethod
    def repository_id(cls) -> str:
        """Generate repository ID."""
        return str(uuid4())

    @classmethod
    def pull_request_id(cls) -> str:
        """Generate pull request ID."""
        return str(uuid4())

    @classmethod
    def pull_request_number(cls) -> int:
        """Generate pull request number."""
        return cls.__faker__.random_int(min=1, max=9999)

    @classmethod
    def platform(cls) -> str:
        """Generate platform."""
        return cls.__faker__.random_element(elements=("github", "gitlab"))

    @classmethod
    def organization(cls) -> str:
        """Generate organization name."""
        return cls.__faker__.user_name()

    @classmethod
    def repository(cls) -> str:
        """Generate repository name."""
        words = cls.__faker__.words(nb=2)
        return "-".join(words)

    @classmethod
    def source_branch(cls) -> str:
        """Generate source branch name."""
        return f"feature/{cls.__faker__.word()}"

    @classmethod
    def target_branch(cls) -> str:
        """Generate target branch name."""
        return "main"

    @classmethod
    def commit_sha(cls) -> str:
        """Generate commit SHA."""
        return cls.__faker__.sha1()

    @classmethod
    def workflow(cls) -> str:
        """Generate workflow name."""
        return "review"

    @classmethod
    def triggered_by(cls) -> str:
        """Generate triggered by user."""
        return cls.__faker__.email()

    @classmethod
    def triggered_at(cls) -> datetime:
        """Generate triggered at timestamp."""
        return datetime.now(UTC)

    @classmethod
    def context(cls) -> dict:
        """Generate context."""
        return {}


class ExecutionStatusMessageFactory(ModelFactory[ExecutionStatusMessage]):
    """Factory for creating ExecutionStatusMessage instances."""

    __model__ = ExecutionStatusMessage
    __check_model__ = False

    @classmethod
    def execution_id(cls) -> str:
        """Generate execution ID."""
        return str(uuid4())

    @classmethod
    def container_id(cls) -> str:
        """Generate container ID."""
        return cls.__faker__.sha256()[:64]

    @classmethod
    def status(cls) -> str:
        """Generate status."""
        return cls.__faker__.random_element(elements=("running", "completed", "failed"))

    @classmethod
    def exit_code(cls) -> int | None:
        """Generate exit code."""
        return 0

    @classmethod
    def error_message(cls) -> str | None:
        """Generate error message."""
        return None

    @classmethod
    def result(cls) -> dict | None:
        """Generate result."""
        return None

    @classmethod
    def timestamp(cls) -> datetime:
        """Generate timestamp."""
        return datetime.now(UTC)


class OrganizationEventMessageFactory(ModelFactory[OrganizationEventMessage]):
    """Factory for creating OrganizationEventMessage instances."""

    __model__ = OrganizationEventMessage
    __check_model__ = False

    @classmethod
    def user_id(cls) -> str:
        """Generate user ID."""
        return str(uuid4())

    @classmethod
    def action(cls) -> str:
        """Generate action type."""
        return cls.__faker__.random_element(elements=("created", "updated", "deleted"))

    @classmethod
    def organization(cls) -> dict:
        """Generate organization data."""
        return {
            "id": str(uuid4()),
            "name": cls.__faker__.company(),
            "provider": "github",
        }

    @classmethod
    def timestamp(cls) -> str | None:
        """Generate timestamp."""
        return datetime.now(UTC).isoformat()


class RepositoryEventMessageFactory(ModelFactory[RepositoryEventMessage]):
    """Factory for creating RepositoryEventMessage instances."""

    __model__ = RepositoryEventMessage
    __check_model__ = False

    @classmethod
    def organization_id(cls) -> str:
        """Generate organization ID."""
        return str(uuid4())

    @classmethod
    def action(cls) -> str:
        """Generate action type."""
        return cls.__faker__.random_element(elements=("created", "updated", "deleted"))

    @classmethod
    def repository(cls) -> dict:
        """Generate repository data."""
        return {
            "id": str(uuid4()),
            "name": "-".join(cls.__faker__.words(nb=2)),
            "external_repo_id": str(cls.__faker__.random_int(min=100000, max=999999)),
            "web_url": f"https://github.com/{cls.__faker__.user_name()}/{cls.__faker__.word()}",
            "provider": "github",
        }

    @classmethod
    def timestamp(cls) -> str | None:
        """Generate timestamp."""
        return datetime.now(UTC).isoformat()


class PullRequestEventMessageFactory(ModelFactory[PullRequestEventMessage]):
    """Factory for creating PullRequestEventMessage instances."""

    __model__ = PullRequestEventMessage
    __check_model__ = False

    @classmethod
    def pull_request_id(cls) -> str:
        """Generate pull request ID."""
        return str(uuid4())

    @classmethod
    def action(cls) -> str:
        """Generate action type."""
        return cls.__faker__.random_element(
            elements=("execution_created", "execution_status_changed")
        )

    @classmethod
    def organization_id(cls) -> str | None:
        """Generate organization ID."""
        return str(uuid4())

    @classmethod
    def repository_id(cls) -> str | None:
        """Generate repository ID."""
        return str(uuid4())

    @classmethod
    def latest_execution_id(cls) -> str | None:
        """Generate latest execution ID."""
        return str(uuid4())

    @classmethod
    def latest_execution_status(cls) -> str | None:
        """Generate latest execution status."""
        return cls.__faker__.random_element(
            elements=("queued", "processing", "completed", "failed")
        )

    @classmethod
    def latest_execution_created_at(cls) -> str | None:
        """Generate latest execution creation timestamp."""
        return datetime.now(UTC).isoformat()

    @classmethod
    def updated_at(cls) -> str | None:
        """Generate update timestamp."""
        return datetime.now(UTC).isoformat()


class GitHubSyncInstallationMessageFactory(ModelFactory[GitHubSyncInstallationMessage]):
    """Factory for creating GitHubSyncInstallationMessage instances."""

    __model__ = GitHubSyncInstallationMessage
    __check_model__ = False

    @classmethod
    def installation_id(cls) -> str:
        """Generate installation ID."""
        return str(cls.__faker__.random_int(min=100000, max=999999))

    @classmethod
    def sender_github_id(cls) -> str | None:
        """Generate sender GitHub ID."""
        return str(cls.__faker__.random_int(min=1000, max=99999))


class GitHubSyncRepositoryPRsMessageFactory(ModelFactory[GitHubSyncRepositoryPRsMessage]):
    """Factory for creating GitHubSyncRepositoryPRsMessage instances."""

    __model__ = GitHubSyncRepositoryPRsMessage
    __check_model__ = False

    @classmethod
    def repository_id(cls) -> str:
        """Generate repository ID."""
        return str(uuid4())

    @classmethod
    def installation_id(cls) -> str:
        """Generate installation ID."""
        return str(cls.__faker__.random_int(min=100000, max=999999))

    @classmethod
    def owner(cls) -> str:
        """Generate repository owner."""
        return cls.__faker__.user_name()

    @classmethod
    def repo_name(cls) -> str:
        """Generate repository name."""
        return "-".join(cls.__faker__.words(nb=2))


class GitLabSyncGroupMessageFactory(ModelFactory[GitLabSyncGroupMessage]):
    """Factory for creating GitLabSyncGroupMessage instances."""

    __model__ = GitLabSyncGroupMessage
    __check_model__ = False

    @classmethod
    def organization_id(cls) -> str:
        """Generate organization ID."""
        return str(uuid4())

    @classmethod
    def repository_ids(cls) -> list[str]:
        """Generate list of repository IDs."""
        return [str(uuid4()) for _ in range(cls.__faker__.random_int(min=1, max=5))]


class GitLabSyncRepositoryMRsMessageFactory(ModelFactory[GitLabSyncRepositoryMRsMessage]):
    """Factory for creating GitLabSyncRepositoryMRsMessage instances."""

    __model__ = GitLabSyncRepositoryMRsMessage
    __check_model__ = False

    @classmethod
    def repository_id(cls) -> str:
        """Generate repository ID."""
        return str(uuid4())

    @classmethod
    def organization_id(cls) -> str:
        """Generate organization ID."""
        return str(uuid4())

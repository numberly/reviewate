"""Shared utilities for container backends (Docker, Kubernetes)."""

import json
import logging
import re
from typing import TYPE_CHECKING, Any
from uuid import UUID

from api.context import get_current_app
from api.database.organization import db_get_organization_by_id
from api.database.repository import db_get_repository_by_id

if TYPE_CHECKING:
    from api.routers.queue.schemas import ReviewJobMessage

logger = logging.getLogger(__name__)

# Regex patterns for parsing structured logs from code_reviewer
RESULT_PATTERN = re.compile(r"\[REVIEWATE:RESULT\]\s*(.+)")
ERROR_PATTERN = re.compile(r"\[REVIEWATE:ERROR\]\s*(.+)")
STATUS_PATTERN = re.compile(r"\[REVIEWATE:STATUS\]\s*(.+)")

# Label keys used to identify reviewate containers
LABEL_EXECUTION_ID = "reviewate.execution_id"
LABEL_ORGANIZATION_ID = "reviewate.organization_id"
LABEL_REPOSITORY_ID = "reviewate.repository_id"
LABEL_PULL_REQUEST_ID = "reviewate.pull_request_id"


def parse_memory_limit(memory_str: str) -> int:
    """Parse memory limit string to bytes.

    Supports common suffixes: k/K (kilobytes), m/M (megabytes), g/G (gigabytes).

    Args:
        memory_str: Memory string like '2g', '512m', '1024k', or raw bytes '1073741824'

    Returns:
        Memory in bytes

    Examples:
        >>> parse_memory_limit("2g")
        2147483648
        >>> parse_memory_limit("512m")
        536870912
    """
    memory_str = memory_str.lower().strip()
    multipliers = {
        "k": 1024,
        "m": 1024 * 1024,
        "g": 1024 * 1024 * 1024,
    }
    for suffix, multiplier in multipliers.items():
        if memory_str.endswith(suffix):
            return int(float(memory_str[:-1]) * multiplier)
    return int(memory_str)


def parse_structured_logs(
    log_text: str,
) -> tuple[dict[str, Any] | None, tuple[str, str] | None]:
    """Parse structured output from container logs.

    Looks for special markers in the logs:
    - [REVIEWATE:RESULT] {...} - JSON result data
    - [REVIEWATE:ERROR] {...} - JSON or plain text error

    Args:
        log_text: Full log output from container

    Returns:
        Tuple of (result dict or None, error info tuple (error_type, error_message) or None)
    """
    result: dict[str, Any] | None = None
    error_info: tuple[str, str] | None = None

    for line in log_text.split("\n"):
        # Check for result marker
        result_match = RESULT_PATTERN.search(line)
        if result_match:
            try:
                result = json.loads(result_match.group(1))
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse result JSON: {result_match.group(1)}")

        # Check for error marker
        error_match = ERROR_PATTERN.search(line)
        if error_match:
            try:
                error_data = json.loads(error_match.group(1))
                error_type = error_data.get("type", "internal_error")
                error_message = error_data.get("message", str(error_data))
                error_info = (error_type, error_message)
            except json.JSONDecodeError:
                error_info = ("internal_error", error_match.group(1))

    return result, error_info


def determine_execution_status(
    exit_code: int,
    result: dict[str, Any] | None,
    error_info: tuple[str, str] | None,
) -> tuple[str, tuple[str, str] | None]:
    """Determine execution status from container exit code and parsed result.

    Args:
        exit_code: Container exit code (0 = success)
        result: Parsed result dict from logs (or None)
        error_info: Parsed error info tuple (error_type, error_message) or None

    Returns:
        Tuple of (status string, error info tuple or None)
    """
    if exit_code == 0 and result:
        return "completed", None

    if error_info:
        return "failed", error_info

    return "failed", ("container_error", f"Container exited with code {exit_code}")


WORKFLOW_TO_SUBCOMMAND = {"review": "review", "summarize": "summary", "full": "full"}


def build_cli_args(job: ReviewJobMessage) -> list[str]:
    """Build CLI arguments for code_reviewer.

    Args:
        job: Job configuration message

    Returns:
        List of CLI arguments for the code_reviewer entrypoint
    """
    subcommand = WORKFLOW_TO_SUBCOMMAND.get(job.workflow, "review")
    return [
        subcommand,
        f"{job.organization}/{job.repository}",
        "-p",
        str(job.pull_request_number),
        "--platform",
        job.platform,
    ]


def build_container_labels(
    execution_id: str,
    job: ReviewJobMessage,
) -> dict[str, str]:
    """Build container labels for tracking.

    Args:
        execution_id: Unique execution identifier
        job: Job configuration message

    Returns:
        Dictionary of labels to apply to the container
    """
    return {
        LABEL_EXECUTION_ID: execution_id,
        LABEL_ORGANIZATION_ID: str(job.organization_id) if job.organization_id else "",
        LABEL_REPOSITORY_ID: str(job.repository_id) if job.repository_id else "",
        LABEL_PULL_REQUEST_ID: str(job.pull_request_id) if job.pull_request_id else "",
    }


async def get_platform_token(job: ReviewJobMessage) -> str | None:
    """Get the platform access token for the job.

    For GitHub: Gets an installation access token using the GitHub App.
    For GitLab: Gets the PAT from the database (org or repo level).

    Args:
        job: Job configuration message

    Returns:
        Platform access token or None if unavailable
    """
    app = get_current_app()

    if job.platform == "github":
        return await _get_github_token(job, app)
    else:
        return _get_gitlab_token(job, app)


async def _get_github_token(job: ReviewJobMessage, app: Any) -> str | None:
    """Get GitHub installation access token.

    Args:
        job: Job configuration message
        app: Application instance

    Returns:
        GitHub installation token or None
    """
    try:
        org_id = UUID(job.organization_id)

        # Look up the organization to get its installation_id
        with app.database.session() as db:
            org = db_get_organization_by_id(db, org_id)
            if not org or not org.installation_id:
                logger.error(f"Organization {org_id} has no GitHub installation_id")
                return None
            installation_id = org.installation_id

        # Get installation access token from GitHub
        return await app.github.get_installation_access_token(installation_id)

    except Exception as e:
        logger.error(f"Failed to get GitHub installation token: {e}")
        return None


def _get_gitlab_token(job: ReviewJobMessage, app: Any) -> str | None:
    """Get GitLab access token from database.

    Tries organization token first, falls back to repository token.

    Args:
        job: Job configuration message
        app: Application instance

    Returns:
        GitLab PAT or None
    """
    try:
        org_id = UUID(job.organization_id)
        repo_id = UUID(job.repository_id) if job.repository_id else None

        with app.database.session() as db:
            org = db_get_organization_by_id(db, org_id)
            repo = db_get_repository_by_id(db, repo_id) if repo_id else None

            # Prefer org token, fallback to repo token
            encrypted_token = (org.gitlab_access_token_encrypted if org else None) or (
                repo.gitlab_access_token_encrypted if repo else None
            )

            if encrypted_token:
                return app.database.decrypt(encrypted_token)

    except Exception as e:
        logger.error(f"Failed to get GitLab access token: {e}")

    return None


async def build_env_vars(job: ReviewJobMessage) -> list[str]:
    """Build environment variables for the container.

    Includes LLM API keys and platform access tokens.

    Args:
        job: Job configuration message

    Returns:
        List of environment variable strings (KEY=value)
    """
    app = get_current_app()
    env: list[str] = []

    # LLM credentials and configuration
    code_reviewer_opts = app.options.code_reviewer
    if code_reviewer_opts.oauth_token:
        # OAuth takes priority — don't pass API key or base URL
        env.append(f"CLAUDE_CODE_OAUTH_TOKEN={code_reviewer_opts.oauth_token}")
    else:
        if code_reviewer_opts.anthropic_api_key:
            env.append(f"ANTHROPIC_API_KEY={code_reviewer_opts.anthropic_api_key}")
        if code_reviewer_opts.anthropic_base_url:
            env.append(f"REVIEWATE_BASE_URL={code_reviewer_opts.anthropic_base_url}")
    if code_reviewer_opts.review_model:
        env.append(f"REVIEWATE_REVIEW_MODEL={code_reviewer_opts.review_model}")
    if code_reviewer_opts.utility_model:
        env.append(f"REVIEWATE_UTILITY_MODEL={code_reviewer_opts.utility_model}")

    # Platform access token (GITHUB_TOKEN for gh CLI, GITLAB_TOKEN for glab CLI)
    platform_token = await get_platform_token(job)
    if platform_token:
        if job.platform == "github":
            env.append(f"GITHUB_TOKEN={platform_token}")
        else:
            env.append(f"GITLAB_TOKEN={platform_token}")

    # GitLab host for self-hosted instances
    if job.platform == "gitlab":
        gitlab_plugin = app.gitlab
        if gitlab_plugin:
            base_url = gitlab_plugin._get_base_url()
            if base_url and "gitlab.com" not in base_url:
                env.append(f"GITLAB_HOST={base_url}")

    # Linked repositories for cross-repo context
    if job.linked_repos:
        env.append(f"LINKED_REPOS={json.dumps([lr.model_dump() for lr in job.linked_repos])}")

    # Team guidelines from feedback summarization
    if job.team_guidelines:
        env.append(f"TEAM_GUIDELINES={job.team_guidelines}")

    return env

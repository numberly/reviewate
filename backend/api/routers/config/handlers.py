"""Route handlers for application configuration."""

from fastapi import APIRouter

from api.context import get_current_app

from .schemas import AppConfig, ProviderConfig

router = APIRouter(prefix="/config", tags=["Config"])


@router.get(
    "",
    operation_id="get_app_config",
    name="get_app_config",
    summary="Get application configuration",
    description="Returns application configuration including enabled providers.",
    response_model=AppConfig,
    status_code=200,
)
async def get_app_config() -> AppConfig:
    """Get application configuration.

    Returns provider availability flags so frontend can show/hide
    provider-specific UI elements.

    Returns:
        AppConfig with provider availability flags
    """
    app = get_current_app()

    # Get GitLab instance URL if plugin is enabled
    gitlab_url = None
    if app.gitlab and app.gitlab.config.oauth:
        gitlab_url = app.gitlab.config.oauth.instance_url

    return AppConfig(
        providers=ProviderConfig(
            github_enabled=app.github is not None,
            gitlab_enabled=app.gitlab is not None,
            google_enabled=app.google is not None,
            gitlab_url=gitlab_url,
        )
    )

"""API route handlers for pull requests endpoints."""

import asyncio
import json
import logging
import time
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from urllib.parse import urlparse
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from faststream.redis import RedisBroker
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from api.context import get_current_app
from api.database import (
    db_get_dashboard_stats,
    db_get_effective_linked_repos,
    db_get_membership_by_username,
    db_get_organization_by_id,
    db_get_pull_requests_for_organizations,
    db_get_pull_requests_with_latest_execution,
    db_get_repository_by_id,
    get_session,
)
from api.database.execution import db_create_execution
from api.jobs.summarize_feedback import get_or_refresh_team_guidelines
from api.models import PullRequest, User
from api.plugins.faststream import get_faststream_broker
from api.plugins.faststream.config import STREAM_MAXLEN
from api.routers.auth import get_current_user
from api.routers.base_schema import (
    ListMetaResponse,
    ListPaginatedResponse,
    PaginationMeta,
)
from api.routers.pull_requests import consumer
from api.routers.queue.schemas import LinkedRepoMessage, ReviewJobMessage
from api.routers.repositories.dependencies import verify_repository_access
from api.utils import parse_uuid

from .dependencies import get_user_org_ids, verify_pull_request_access
from .schemas import (
    DashboardStatsResponse,
    PullRequestDetail,
    PullRequestListItem,
    StatChange,
    TriggerReviewRequest,
    TriggerReviewResponse,
)

router = APIRouter(tags=["Pull Requests"])
logger = logging.getLogger(__name__)


def _build_author_disabled_map(db: Session, prs_with_exec: list[tuple]) -> dict[str, bool]:
    """Build a map of author → reviewate_disabled for a batch of PRs."""
    result: dict[str, bool] = {}
    for pr, _ in prs_with_exec:
        if pr.author not in result:
            membership = db_get_membership_by_username(db, pr.organization_id, pr.author)
            result[pr.author] = membership is not None and not membership.reviewate_enabled
    return result


def _strip_error_details_if_needed(items: list[PullRequestListItem]) -> None:
    """Strip error_detail from items if config disables exposure."""
    try:
        app = get_current_app()
        if not app.options.expose_error_details:
            for item in items:
                item.latest_execution_error_detail = None
    except Exception:
        pass


@router.get(
    "/pull-requests/stream",
    operation_id="dashboard_stream",
    name="dashboard_pull_requests_stream",
    summary="Stream all pull request updates for dashboard",
    description="Server-Sent Events stream for real-time updates of all PRs across user's organizations.",
)
async def dashboard_pull_requests_stream(
    org_uuids: list[UUID] = Depends(get_user_org_ids),
    current_user: User = Depends(get_current_user),
) -> EventSourceResponse:
    """Stream all PR updates for the user's organizations via SSE."""
    org_ids = [str(org_id) for org_id in org_uuids]

    async def event_generator() -> AsyncGenerator:
        """Generate SSE events for all PR updates across user's orgs."""
        user_queue = consumer.register_client(user_id=str(current_user.id))

        try:
            yield {
                "event": "connected",
                "data": f'{{"user_id": "{current_user.id}", "organizations": {len(org_ids)}}}',
            }

            while True:
                try:
                    event_data = await asyncio.wait_for(user_queue.get(), timeout=30.0)
                except TimeoutError:
                    yield {"event": "keepalive", "data": ""}
                    continue

                if event_data.get("__sse_shutdown__"):
                    logger.debug(f"SSE shutdown signal received for user {current_user.id}")
                    break

                pr_org_id = event_data.get("organization_id")
                if pr_org_id and pr_org_id in org_ids:
                    yield {
                        "event": "pr_update",
                        "data": json.dumps(event_data),
                    }

        except asyncio.CancelledError:
            logger.debug(f"Dashboard SSE connection closed for user {current_user.id}")
            raise
        finally:
            consumer.unregister_client(str(current_user.id), user_queue)

    return EventSourceResponse(event_generator())


@router.get(
    "/pull-requests",
    operation_id="list_all_pull_requests",
    name="list_all_pull_requests",
    summary="List all pull requests for user",
    description="Lists all pull requests across all organizations the user has access to, with pagination, filtering, and latest execution status.",
    response_model=ListPaginatedResponse[PullRequestListItem],
    status_code=200,
)
async def list_all_pull_requests(
    limit: int = 100,
    page: int = 1,
    state: str | None = None,
    created_after: datetime | None = None,
    search: str | None = None,
    repository_ids: list[str] | None = Query(default=None, description="Filter by repository IDs"),
    author: list[str] | None = Query(default=None, description="Filter by PR author username(s)"),
    organization_id: str | None = Query(default=None, description="Filter by organization ID"),
    org_ids: list[UUID] = Depends(get_user_org_ids),
    db: Session = Depends(get_session),
) -> ListPaginatedResponse[PullRequestListItem]:
    """List all pull requests across all user's organizations."""
    # If organization_id filter provided, validate access and use only that org
    if organization_id:
        org_uuid = parse_uuid(organization_id, "organization ID")
        if org_uuid not in org_ids:
            raise HTTPException(status_code=403, detail="Access denied to organization")
        org_ids = [org_uuid]

    if not org_ids:
        return ListPaginatedResponse(
            objects=[],
            meta=ListMetaResponse(timestamp=time.time()),
            pagination=PaginationMeta(total=0, limit=limit, page=page),
        )

    offset = (page - 1) * limit

    repo_uuids = None
    if repository_ids:
        repo_uuids = [parse_uuid(rid, "repository ID") for rid in repository_ids]

    prs_with_exec, total_count = db_get_pull_requests_for_organizations(
        db,
        org_ids,
        limit=limit,
        offset=offset,
        state=state,
        created_after=created_after,
        search=search,
        repository_ids=repo_uuids,
        author=author,
    )

    author_disabled_map = _build_author_disabled_map(db, prs_with_exec)

    items = [
        PullRequestListItem.from_pr_with_execution(
            pr,
            latest_exec,
            author_reviewate_disabled=author_disabled_map.get(pr.author, False),
        )
        for pr, latest_exec in prs_with_exec
    ]

    _strip_error_details_if_needed(items)

    return ListPaginatedResponse(
        objects=items,
        meta=ListMetaResponse(timestamp=time.time()),
        pagination=PaginationMeta(total=total_count, limit=limit, page=page),
    )


def _calc_change(current: float | int | None, previous: float | int | None) -> StatChange:
    """Calculate week-over-week percentage change."""
    if current is None or previous is None:
        return StatChange(percentage=None, trend="neutral")
    if previous == 0:
        if current == 0:
            return StatChange(percentage=None, trend="neutral")
        return StatChange(percentage=None, trend="up")
    pct = round(((current - previous) / previous) * 100, 1)
    if pct > 0:
        return StatChange(percentage=pct, trend="up")
    elif pct < 0:
        return StatChange(percentage=pct, trend="down")
    return StatChange(percentage=pct, trend="neutral")


@router.get(
    "/pull-requests/stats",
    operation_id="get_dashboard_stats",
    name="get_dashboard_stats",
    summary="Get dashboard statistics",
    description="Returns aggregated dashboard stats (active repos, avg review time, PRs reviewed) with week-over-week changes.",
    response_model=DashboardStatsResponse,
    status_code=200,
)
async def get_dashboard_stats(
    org_ids: list[UUID] = Depends(get_user_org_ids),
    db: Session = Depends(get_session),
) -> DashboardStatsResponse:
    """Get dashboard statistics for the authenticated user's organizations."""
    raw = db_get_dashboard_stats(db, org_ids)

    return DashboardStatsResponse(
        active_repos=raw["active_repos"],
        active_repos_change=_calc_change(raw["active_repos"], raw["prev_active_repos"]),
        avg_review_time_seconds=raw["avg_review_time_seconds"],
        avg_review_time_change=_calc_change(
            raw["avg_review_time_seconds"], raw["prev_avg_review_time_seconds"]
        ),
        prs_reviewed=raw["prs_reviewed"],
        prs_reviewed_change=_calc_change(raw["prs_reviewed"], raw["prev_prs_reviewed"]),
    )


@router.get(
    "/repositories/{repo_id}/pull-requests",
    operation_id="list_pull_requests",
    name="list_repository_pull_requests",
    summary="List repository pull requests",
    description="Lists pull requests for a repository with pagination and their latest execution status.",
    response_model=ListPaginatedResponse[PullRequestListItem],
    status_code=200,
)
async def list_repository_pull_requests(
    repo_access: tuple = Depends(verify_repository_access),
    limit: int = 20,
    page: int = 1,
    db: Session = Depends(get_session),
) -> ListPaginatedResponse[PullRequestListItem]:
    """List pull requests for a repository with pagination and latest execution status."""
    repository, _membership = repo_access

    offset = (page - 1) * limit

    prs_with_exec, total_count = db_get_pull_requests_with_latest_execution(
        db, repository.id, limit=limit, offset=offset
    )

    author_disabled_map = _build_author_disabled_map(db, prs_with_exec)

    items = [
        PullRequestListItem.from_pr_with_execution(
            pr,
            latest_exec,
            author_reviewate_disabled=author_disabled_map.get(pr.author, False),
        )
        for pr, latest_exec in prs_with_exec
    ]

    _strip_error_details_if_needed(items)

    return ListPaginatedResponse(
        objects=items,
        meta=ListMetaResponse(timestamp=time.time()),
        pagination=PaginationMeta(total=total_count, limit=limit, page=page),
    )


@router.get(
    "/pull-requests/{pr_id}",
    operation_id="get_pull_request",
    name="get_pull_request",
    summary="Get pull request details",
    description="Gets detailed information about a single pull request.",
    response_model=PullRequestDetail,
    status_code=200,
)
async def get_pull_request(
    pr: PullRequest = Depends(verify_pull_request_access),
    db: Session = Depends(get_session),
) -> PullRequestDetail:
    """Get single pull request details."""
    author_membership = db_get_membership_by_username(db, pr.organization_id, pr.author)
    author_reviewate_disabled = (
        author_membership is not None and not author_membership.reviewate_enabled
    )

    return PullRequestDetail.from_pr(pr, author_reviewate_disabled=author_reviewate_disabled)


@router.post(
    "/pull-requests/{pr_id}/review",
    operation_id="trigger_review",
    name="trigger_pull_request_review",
    summary="Trigger a code review",
    description="Manually triggers a code review for a pull request by queueing a review job.",
    response_model=TriggerReviewResponse,
    status_code=202,
)
async def trigger_pull_request_review(
    pr: PullRequest = Depends(verify_pull_request_access),
    broker: RedisBroker = Depends(get_faststream_broker),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
    request: TriggerReviewRequest = Body(...),
) -> TriggerReviewResponse:
    """Trigger a code review for a pull request."""
    # Check that the requester is the PR author
    author_usernames = {
        identity.username for identity in current_user.identities if identity.username
    }
    if pr.author not in author_usernames:
        raise HTTPException(
            status_code=403, detail="Only the PR author can trigger a manual review"
        )

    # Get repository for organization info
    repository = db_get_repository_by_id(db, pr.repository_id)
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")

    organization = db_get_organization_by_id(db, repository.organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Check if the PR author has reviews disabled
    author_membership = db_get_membership_by_username(db, organization.id, pr.author)
    if author_membership and not author_membership.reviewate_enabled:
        raise HTTPException(
            status_code=403,
            detail=f"Reviews are disabled for user '{pr.author}'. An admin can enable reviews in the organization's Team settings.",
        )

    # Create execution record immediately
    execution = db_create_execution(
        db=db,
        organization_id=repository.organization_id,
        repository_id=repository.id,
        pull_request_id=pr.id,
        pr_number=pr.pr_number,
        commit_sha=request.commit_sha,
        status="queued",
    )

    job_id = str(execution.id)
    parsed_url = urlparse(repository.web_url)
    repo_path = parsed_url.path.strip("/")

    path_parts = repo_path.split("/", 1)
    repo_owner = path_parts[0] if path_parts else organization.name
    repo_name = path_parts[1] if len(path_parts) > 1 else repository.name

    # Get effective linked repos (org + repo level, deduplicated)
    linked_repos_db = db_get_effective_linked_repos(db, repository.id)
    linked_repos_messages = [
        LinkedRepoMessage(
            provider=lr.linked_provider,
            provider_url=lr.linked_provider_url,
            repo_path=lr.linked_repo_path,
            branch=lr.linked_branch,
            display_name=lr.display_name,
            name=lr.display_name or lr.linked_repo_path.split("/")[-1],
        )
        for lr in linked_repos_db
    ]

    # Get team guidelines (lazy refresh if stale and feedback exists)
    team_guidelines = await get_or_refresh_team_guidelines(
        organization_id=organization.id,
        repository_id=repository.id,
    )

    message = ReviewJobMessage(
        job_id=job_id,
        organization_id=str(organization.id),
        repository_id=str(repository.id),
        pull_request_id=str(pr.id),
        pull_request_number=pr.pr_number,
        platform=organization.provider,
        organization=repo_owner,
        repository=repo_name,
        source_branch=pr.head_branch,
        target_branch=pr.base_branch,
        commit_sha=request.commit_sha,
        workflow="review",
        triggered_by=current_user.email or current_user.display_username,
        triggered_at=datetime.now(UTC),
        context={
            "manual_trigger": True,
            "pr_url": pr.pr_url,
            "title": pr.title,
        },
        linked_repos=linked_repos_messages,
        team_guidelines=team_guidelines,
    )

    # Publish job message to review queue
    try:
        await broker.publish(
            message.model_dump(), stream="reviewate.review.jobs", maxlen=STREAM_MAXLEN
        )
        logger.debug(f"Published review job {job_id} to queue")
    except Exception as e:
        logger.exception("Failed to publish review job to queue", extra={"job_id": job_id})
        raise HTTPException(
            status_code=500,
            detail=f"Failed to queue review job: {e!s}",
        ) from e

    # Publish PR update event to sync latest execution info
    try:
        pr_event_data = {
            "pull_request_id": str(pr.id),
            "organization_id": str(pr.organization_id),
            "repository_id": str(pr.repository_id),
            "action": "execution_created",
            "latest_execution_id": str(execution.id),
            "latest_execution_status": "queued",
            "latest_execution_created_at": execution.created_at.isoformat(),
            "updated_at": pr.updated_at.isoformat(),
        }
        await broker.publish(pr_event_data, channel="reviewate.events.pull_requests")
        logger.debug(f"Published PR update event for new execution on PR {pr.id}")
    except Exception as e:
        logger.error(
            f"Failed to publish PR update event: {e}",
            extra={"pull_request_id": str(pr.id), "execution_id": str(execution.id)},
        )

    return TriggerReviewResponse(
        execution_id=str(execution.id),
        pull_request_id=str(pr.id),
        status="queued",
        commit_sha=request.commit_sha,
        created_at=execution.created_at,
    )

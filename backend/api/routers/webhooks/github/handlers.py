"""GitHub webhook handlers.

This module handles all GitHub webhook events through a unified router.
"""

import json
import logging

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session

from api.database import get_session

from ..utils import WebhookResponse
from .dependencies import verify_github_webhook
from .feedback import (
    handle_issue_comment_event,
    handle_pull_request_review_comment_event,
    handle_pull_request_review_event,
)
from .installations import (
    handle_installation_created,
    handle_installation_deleted,
    handle_repositories_added,
    handle_repositories_removed,
)
from .pull_requests import handle_pull_request_event
from .schemas import (
    GitHubAppInstallationEvent,
    GitHubAppInstallationRepositoriesEvent,
    GitHubIssueCommentEvent,
    GitHubPullRequestEvent,
    GitHubPullRequestReviewCommentEvent,
    GitHubPullRequestReviewEvent,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/github", tags=["Webhooks", "GitHub"], dependencies=[Depends(verify_github_webhook)]
)


@router.post(
    "",
    operation_id="github_webhook",
    name="github_webhook",
    summary="GitHub webhook router",
    description=(
        "Unified webhook endpoint for all GitHub events. Routes events based on "
        "X-GitHub-Event header to appropriate handlers (installation, pull_request, etc.)"
    ),
    response_model=WebhookResponse,
    status_code=202,
)
async def github_webhook(
    request: Request,
    x_github_event: str = Header(..., description="GitHub event type"),
    db: Session = Depends(get_session),
) -> WebhookResponse:
    """Unified GitHub webhook router that handles all GitHub events.

    This endpoint receives all GitHub webhook events and routes them to
    appropriate handlers based on the X-GitHub-Event header.

    Args:
        request: FastAPI request object
        x_github_event: Event type from GitHub header (installation, pull_request, etc.)
        db: Database session

    Returns:
        WebhookResponse confirmation (202 Accepted)

    Raises:
        HTTPException: 401 if signature verification fails, 404 if not configured
    """
    body = await request.body()

    # Route based on GitHub event type
    match x_github_event:
        case "installation":
            # Parse as installation event
            event_data = json.loads(body)
            installation_event = GitHubAppInstallationEvent(**event_data)

            # Route to appropriate installation handler
            match installation_event.action:
                case "created":
                    return await handle_installation_created(installation_event, db)
                case "deleted":
                    return await handle_installation_deleted(installation_event, db)
                case _:
                    return WebhookResponse(
                        message=f"Installation action '{installation_event.action}' received but not processed",
                        processed=False,
                    )

        case "installation_repositories":
            # Parse as installation_repositories event
            event_data = json.loads(body)
            repo_event = GitHubAppInstallationRepositoriesEvent(**event_data)

            # Route to appropriate repositories handler
            match repo_event.action:
                case "added":
                    return await handle_repositories_added(repo_event, db)
                case "removed":
                    return await handle_repositories_removed(repo_event, db)
                case _:
                    return WebhookResponse(
                        message=f"Installation repositories action '{repo_event.action}' received but not processed",
                        processed=False,
                    )

        case "pull_request":
            # Parse as pull request event
            event_data = json.loads(body)
            pr_event = GitHubPullRequestEvent(**event_data)

            # Handle pull request event
            return await handle_pull_request_event(pr_event, db)

        case "issue_comment":
            # Parse as issue comment event (for feedback on PR comments)
            event_data = json.loads(body)
            comment_event = GitHubIssueCommentEvent(**event_data)
            return await handle_issue_comment_event(comment_event, db)

        case "pull_request_review_comment":
            # Parse as PR review comment event (for reactions on review comments)
            event_data = json.loads(body)
            review_comment_event = GitHubPullRequestReviewCommentEvent(**event_data)
            return await handle_pull_request_review_comment_event(review_comment_event, db)

        case "pull_request_review":
            # Parse as PR review event (for dismissed reviews)
            event_data = json.loads(body)
            review_event = GitHubPullRequestReviewEvent(**event_data)
            return await handle_pull_request_review_event(review_event, db)

        case _:
            return WebhookResponse(
                message=f"Event type '{x_github_event}' not supported",
                processed=False,
            )

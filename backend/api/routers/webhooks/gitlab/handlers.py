"""GitLab webhook handlers.

This module handles all GitLab webhook events.
"""

import json
import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from api.database import get_session

from ..utils import WebhookResponse
from .dependencies import verify_gitlab_webhook
from .feedback import handle_note_event
from .merge_requests import handle_merge_request_event
from .schemas import (
    GitLabMergeRequestEvent,
    GitLabNoteEvent,
)

logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/gitlab", tags=["Webhooks", "GitLab"], dependencies=[Depends(verify_gitlab_webhook)]
)


@router.post(
    "",
    operation_id="gitlab_webhook",
    name="gitlab_webhook",
    summary="GitLab webhook router",
    description=(
        "Unified webhook endpoint for all GitLab events. Currently handles merge request events."
    ),
    response_model=WebhookResponse,
    status_code=202,
)
async def gitlab_webhook(
    request: Request,
    db: Session = Depends(get_session),
) -> WebhookResponse:
    """Handle GitLab webhook events and route to appropriate handlers.

    Args:
        request: FastAPI request object
        db: Database session

    Returns:
        WebhookResponse confirmation (202 Accepted)

    Raises:
        HTTPException: 401 if token invalid, 404 if not configured
    """
    body = await request.body()

    # Parse event to determine type
    event_data = json.loads(body)
    object_kind = event_data.get("object_kind", "")

    # Route based on event type
    if object_kind == "merge_request":
        event = GitLabMergeRequestEvent(**event_data)
        return await handle_merge_request_event(event, db)
    elif object_kind == "note":
        note_event = GitLabNoteEvent(**event_data)
        return await handle_note_event(note_event, db)
    else:
        return WebhookResponse(
            message=f"Event type '{object_kind}' not supported",
            processed=False,
        )

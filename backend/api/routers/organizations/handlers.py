import asyncio
import logging
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from api.database import (
    db_get_organization_by_id,
    db_get_organization_members,
    db_get_organization_membership_by_id,
    db_get_organization_memberships_by_identity,
    db_get_user_organization_ids,
    db_update_member_settings,
    db_update_organization_settings,
    get_session,
)
from api.models import Organization, OrganizationMembership, User
from api.routers.auth import get_current_user
from api.routers.base_schema import ListGenericResponse
from api.routers.sources.schemas import OrganizationListItem
from api.sse import make_sse_event
from api.utils import parse_uuid

from . import consumer as org_consumer
from .dependencies import verify_organization_access, verify_organization_admin
from .schemas import (
    MemberListItem,
    MemberSettingsUpdate,
    OrganizationSettings,
    OrganizationSettingsUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/organizations", tags=["Organizations"])


@router.get(
    "",
    operation_id="list_organizations",
    name="list_organizations",
    summary="List user's organizations",
    description="Lists all organizations the authenticated user is a member of.",
    response_model=ListGenericResponse[OrganizationListItem],
    status_code=200,
)
async def list_organizations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> ListGenericResponse[OrganizationListItem]:
    identities = current_user.identities
    identity_ids = [identity.id for identity in identities]

    org_ids = db_get_user_organization_ids(db, identity_ids)
    organizations = db.query(Organization).filter(Organization.id.in_(org_ids)).all()

    org_items = []
    for org in organizations:
        membership = db_get_organization_memberships_by_identity(db, identity_ids, org.id)
        role = membership.role if membership else "member"

        org_items.append(
            OrganizationListItem(
                id=org.id,
                name=org.name,
                external_org_id=org.external_org_id,
                installation_id=org.installation_id,
                provider=org.provider,
                avatar_url=org.avatar_url,
                created_at=org.created_at,
                role=role,
            )
        )

    return ListGenericResponse(objects=org_items)


@router.get(
    "/stream",
    operation_id="stream_organizations",
    name="stream_organizations",
    summary="Stream organization updates",
    description="Server-Sent Events stream for real-time organization updates for the authenticated user.",
    status_code=200,
)
async def stream_organizations(
    current_user: User = Depends(get_current_user),
) -> EventSourceResponse:
    user_id = str(current_user.id)

    async def event_generator() -> AsyncGenerator[dict[str, str]]:
        queue = org_consumer.register_client(user_id)

        try:
            yield make_sse_event(
                "connected", {"user_id": user_id, "message": "Streaming organization updates"}
            )

            while True:
                try:
                    event_data = await asyncio.wait_for(queue.get(), timeout=30.0)
                except TimeoutError:
                    yield make_sse_event("keepalive", {})
                    continue

                if event_data.get("__sse_shutdown__"):
                    logger.debug(f"SSE shutdown signal received for user {user_id}")
                    break

                yield make_sse_event("org_update", event_data)

        except asyncio.CancelledError:
            logger.debug(f"SSE client disconnected for user {user_id} (organizations)")
            raise
        except Exception as e:
            logger.error(f"SSE error for user {user_id} (organizations): {e}", exc_info=True)
            yield make_sse_event("error", {"error": str(e)})
        finally:
            org_consumer.unregister_client(user_id, queue)

    return EventSourceResponse(event_generator())


@router.get(
    "/{org_id}/settings",
    operation_id="get_organization_settings",
    name="get_organization_settings",
    summary="Get organization settings",
    description="Get the current review settings for an organization.",
    response_model=OrganizationSettings,
    status_code=200,
)
async def get_organization_settings(
    membership: OrganizationMembership = Depends(verify_organization_access),
    db: Session = Depends(get_session),
) -> OrganizationSettings:
    organization = db_get_organization_by_id(db, membership.organization_id)
    return OrganizationSettings.model_validate(organization)


@router.patch(
    "/{org_id}/settings",
    operation_id="update_organization_settings",
    name="update_organization_settings",
    summary="Update organization settings",
    description="Update review settings for an organization. Requires admin role.",
    response_model=OrganizationSettings,
    status_code=200,
)
async def update_organization_settings(
    settings: OrganizationSettingsUpdate,
    membership: OrganizationMembership = Depends(verify_organization_admin),
    db: Session = Depends(get_session),
) -> OrganizationSettings:
    update_kwargs = settings.model_dump(exclude_none=True)
    organization = db_update_organization_settings(
        db,
        membership.organization_id,
        **update_kwargs,
    )
    return OrganizationSettings.model_validate(organization)


# Member endpoints


@router.get(
    "/{org_id}/members",
    operation_id="list_organization_members",
    name="list_organization_members",
    summary="List organization members",
    description="List all members of an organization with their settings.",
    response_model=ListGenericResponse[MemberListItem],
    status_code=200,
)
async def list_organization_members(
    membership: OrganizationMembership = Depends(verify_organization_access),
    db: Session = Depends(get_session),
) -> ListGenericResponse[MemberListItem]:
    members = db_get_organization_members(db, membership.organization_id)
    return ListGenericResponse(objects=[MemberListItem.model_validate(m) for m in members])


@router.get(
    "/{org_id}/members/{member_id}",
    operation_id="get_organization_member",
    name="get_organization_member",
    summary="Get organization member",
    description="Get details of a specific organization member.",
    response_model=MemberListItem,
    status_code=200,
)
async def get_organization_member(
    member_id: str = Path(description="Member ID (UUID)"),
    membership: OrganizationMembership = Depends(verify_organization_access),
    db: Session = Depends(get_session),
) -> MemberListItem:
    member_uuid = parse_uuid(member_id, "member ID")
    member = db_get_organization_membership_by_id(db, member_uuid)

    if not member or member.organization_id != membership.organization_id:
        raise HTTPException(status_code=404, detail="Member not found")

    return MemberListItem.model_validate(member)


@router.patch(
    "/{org_id}/members/{member_id}",
    operation_id="update_organization_member",
    name="update_organization_member",
    summary="Update member settings",
    description="Update settings for a specific organization member. Admins can update any member, regular members can only update their own settings.",
    response_model=MemberListItem,
    status_code=200,
)
async def update_organization_member(
    settings: MemberSettingsUpdate,
    member_id: str = Path(description="Member ID (UUID)"),
    membership: OrganizationMembership = Depends(verify_organization_access),
    db: Session = Depends(get_session),
) -> MemberListItem:
    member_uuid = parse_uuid(member_id, "member ID")

    member = db_get_organization_membership_by_id(db, member_uuid)
    if not member or member.organization_id != membership.organization_id:
        raise HTTPException(status_code=404, detail="Member not found")

    is_self = membership.id == member_uuid
    if membership.role != "admin" and not is_self:
        raise HTTPException(
            status_code=403,
            detail="Only admins can update other members' settings",
        )

    update_kwargs = settings.model_dump(exclude_none=True)
    updated_member = db_update_member_settings(db, member_uuid, **update_kwargs)

    if not updated_member:
        raise HTTPException(status_code=404, detail="Member not found")

    return MemberListItem.model_validate(updated_member)

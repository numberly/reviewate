"""API route handlers for linked repositories endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from api.database import (
    db_add_linked_repo,
    db_get_linked_repo_by_id,
    db_get_org_linked_repos,
    db_get_organization_by_id,
    db_get_organization_memberships_by_identity,
    db_get_repo_linked_repos,
    db_get_repository_by_id,
    db_remove_linked_repo,
    get_session,
)
from api.models import OrganizationMembership, Repository, User
from api.routers.auth import get_current_user
from api.routers.base_schema import ListGenericResponse
from api.routers.organizations.dependencies import (
    verify_organization_access,
    verify_organization_admin,
)
from api.routers.repositories.dependencies import verify_repository_access, verify_repository_admin
from api.utils import parse_uuid

from .schemas import (
    DeleteLinkedRepositoryResponse,
    LinkedRepositoryCreate,
    LinkedRepositoryResponse,
)
from .utils import validate_linked_repo_access

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Linked Repositories"])


# Organization-level linked repos endpoints


@router.get(
    "/organizations/{org_id}/linked-repos",
    operation_id="list_organization_linked_repos",
    name="list_organization_linked_repos",
    summary="List organization linked repositories",
    response_model=ListGenericResponse[LinkedRepositoryResponse],
    status_code=200,
)
async def list_organization_linked_repos(
    membership: OrganizationMembership = Depends(verify_organization_access),
    db: Session = Depends(get_session),
) -> ListGenericResponse[LinkedRepositoryResponse]:
    linked_repos = db_get_org_linked_repos(db, membership.organization_id)
    return ListGenericResponse(
        objects=[LinkedRepositoryResponse.model_validate(lr) for lr in linked_repos]
    )


@router.post(
    "/organizations/{org_id}/linked-repos",
    operation_id="add_organization_linked_repo",
    name="add_organization_linked_repo",
    summary="Add organization linked repository",
    response_model=LinkedRepositoryResponse,
    status_code=201,
)
async def add_organization_linked_repo(
    data: LinkedRepositoryCreate,
    membership: OrganizationMembership = Depends(verify_organization_admin),
    db: Session = Depends(get_session),
) -> LinkedRepositoryResponse:
    organization = db_get_organization_by_id(db, membership.organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    parsed = await validate_linked_repo_access(data, organization)

    try:
        linked_repo = db_add_linked_repo(
            db=db,
            organization_id=membership.organization_id,
            linked_provider=parsed.provider,
            linked_provider_url=parsed.provider_url,
            linked_repo_path=parsed.repo_path,
            linked_branch=data.branch,
        )
        return LinkedRepositoryResponse.model_validate(linked_repo)
    except Exception as e:
        if "unique" in str(e).lower():
            raise HTTPException(
                status_code=400,
                detail="This repository is already linked to the organization",
            ) from e
        raise


# Repository-level linked repos endpoints


@router.get(
    "/repositories/{repo_id}/linked-repos",
    operation_id="list_repository_linked_repos",
    name="list_repository_linked_repos",
    summary="List repository linked repositories",
    response_model=ListGenericResponse[LinkedRepositoryResponse],
    status_code=200,
)
async def list_repository_linked_repos(
    repo_access: tuple[Repository, OrganizationMembership] = Depends(verify_repository_access),
    db: Session = Depends(get_session),
) -> ListGenericResponse[LinkedRepositoryResponse]:
    repository, _membership = repo_access
    linked_repos = db_get_repo_linked_repos(db, repository.id)
    return ListGenericResponse(
        objects=[LinkedRepositoryResponse.model_validate(lr) for lr in linked_repos]
    )


@router.post(
    "/repositories/{repo_id}/linked-repos",
    operation_id="add_repository_linked_repo",
    name="add_repository_linked_repo",
    summary="Add repository linked repository",
    response_model=LinkedRepositoryResponse,
    status_code=201,
)
async def add_repository_linked_repo(
    data: LinkedRepositoryCreate,
    repo_access: tuple[Repository, OrganizationMembership] = Depends(verify_repository_admin),
    db: Session = Depends(get_session),
) -> LinkedRepositoryResponse:
    repository, _membership = repo_access

    organization = db_get_organization_by_id(db, repository.organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    parsed = await validate_linked_repo_access(data, organization, repository)

    try:
        linked_repo = db_add_linked_repo(
            db=db,
            repository_id=repository.id,
            linked_provider=parsed.provider,
            linked_provider_url=parsed.provider_url,
            linked_repo_path=parsed.repo_path,
            linked_branch=data.branch,
        )
        return LinkedRepositoryResponse.model_validate(linked_repo)
    except Exception as e:
        if "unique" in str(e).lower():
            raise HTTPException(
                status_code=400,
                detail="This repository is already linked",
            ) from e
        raise


# Shared delete endpoint


@router.delete(
    "/linked-repos/{linked_repo_id}",
    operation_id="delete_linked_repo",
    name="delete_linked_repo",
    summary="Delete linked repository",
    response_model=DeleteLinkedRepositoryResponse,
    status_code=200,
)
async def delete_linked_repo(
    linked_repo_id: str = Path(description="Linked repository ID (UUID)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> DeleteLinkedRepositoryResponse:
    linked_repo_uuid = parse_uuid(linked_repo_id, "linked repository ID")
    linked_repo = db_get_linked_repo_by_id(db, linked_repo_uuid)
    if not linked_repo:
        raise HTTPException(status_code=404, detail="Linked repository not found")

    # Determine parent organization
    if linked_repo.organization_id:
        organization_id = linked_repo.organization_id
    elif linked_repo.repository_id:
        repository = db_get_repository_by_id(db, linked_repo.repository_id)
        if not repository:
            raise HTTPException(status_code=404, detail="Repository not found")
        organization_id = repository.organization_id
    else:
        raise HTTPException(status_code=500, detail="Invalid linked repository state")

    # Verify admin access
    identity_ids = [identity.id for identity in current_user.identities]
    membership = db_get_organization_memberships_by_identity(db, identity_ids, organization_id)
    if not membership:
        raise HTTPException(
            status_code=403, detail="You don't have access to this linked repository"
        )
    if membership.role != "admin":
        raise HTTPException(
            status_code=403, detail="Only organization admins can delete linked repositories"
        )

    db_remove_linked_repo(db, linked_repo_uuid)

    return DeleteLinkedRepositoryResponse(
        message="Linked repository deleted successfully",
        linked_repository_id=linked_repo_id,
    )

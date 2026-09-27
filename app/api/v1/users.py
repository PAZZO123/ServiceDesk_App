import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import ClientInfo, DbSession, RequireUserManager
from app.schemas.common import Page, PaginationParams
from app.schemas.role import RoleAssignment, RoleRead
from app.schemas.user import UserRead
from app.services.role_service import RoleService

router = APIRouter(tags=["Users & Roles"])


def _service(db: DbSession) -> RoleService:
    return RoleService(db)


RoleSvc = Annotated[RoleService, Depends(_service)]


@router.get("/roles", response_model=list[RoleRead], summary="List roles and what they grant")
async def list_roles(svc: RoleSvc, manager: RequireUserManager):
    return await svc.list_roles()


@router.get("/users", response_model=Page[UserRead], summary="List users")
async def list_users(
    svc: RoleSvc,
    manager: RequireUserManager,
    pagination: Annotated[PaginationParams, Depends()],
) -> Page[UserRead]:
    users, total = await svc.list_users(pagination)
    return Page.create(
        items=[UserRead.model_validate(u) for u in users],
        total=total,
        page=pagination.page,
        size=pagination.size,
    )


@router.patch(
    "/users/{user_id}/role",
    response_model=UserRead,
    summary="Change a user's role",
    responses={
        400: {"description": "No such role"},
        403: {"description": "You cannot change your own role"},
    },
)
async def assign_role(
    user_id: uuid.UUID,
    data: RoleAssignment,
    svc: RoleSvc,
    manager: RequireUserManager,
    client: ClientInfo,
):
    return await svc.assign_role(
        user_id, data.role, actor=manager, ip_address=client["ip_address"]
    )

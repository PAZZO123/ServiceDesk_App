import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import (
    ClientInfo,
    RequireRoleManager,
    RequireRoleReader,
    RequireUserManager,
    RoleSvc,
)
from app.schemas.common import Page, PaginationParams
from app.schemas.role import (
    PermissionRead,
    RoleAssignment,
    RoleCreate,
    RolePermissionsUpdate,
    RoleRead,
)
from app.schemas.user import UserRead

router = APIRouter(tags=["Users & Roles"])

@router.get("/roles", response_model=list[RoleRead], summary="List roles and what they grant")
async def list_roles(svc: RoleSvc, reader: RequireRoleReader):
    return await svc.list_roles()


@router.get(
    "/permissions",
    response_model=list[PermissionRead],
    summary="Every permission a role can grant",
)
async def list_permissions(svc: RoleSvc, reader: RequireRoleReader):
    return await svc.list_permissions()


@router.post(
    "/roles",
    response_model=RoleRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a role",
    responses={
        403: {"description": "You may only grant permissions you have yourself"},
        409: {"description": "A role with this name already exists"},
    },
)
async def create_role(
    data: RoleCreate, svc: RoleSvc, manager: RequireRoleManager, client: ClientInfo
):
    return await svc.create_role(data, actor=manager, ip_address=client["ip_address"])


@router.put(
    "/roles/{role_id}/permissions",
    response_model=RoleRead,
    summary="Replace the permissions of a role",
    responses={
        403: {"description": "Your own role, or a permission you do not have"},
        404: {"description": "No such role"},
    },
)
async def set_role_permissions(
    role_id: uuid.UUID,
    data: RolePermissionsUpdate,
    svc: RoleSvc,
    manager: RequireRoleManager,
    client: ClientInfo,
):
    return await svc.set_permissions(
        role_id, data, actor=manager, ip_address=client["ip_address"]
    )


@router.delete(
    "/roles/{role_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a role",
    responses={
        404: {"description": "No such role"},
        409: {"description": "Built-in role, or users still have it"},
    },
)
async def delete_role(
    role_id: uuid.UUID, svc: RoleSvc, manager: RequireRoleManager, client: ClientInfo
) -> None:
    await svc.delete_role(role_id, actor=manager, ip_address=client["ip_address"])


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

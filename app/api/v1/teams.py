import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import ClientInfo, DbSession, RequireAdmin, VerifiedUser
from app.schemas.team import MemberAdd, MemberRead, MemberUpdate
from app.services.team_services import TeamService

router=APIRouter(prefix="/teams", tags=["Teams"])

def _service(db:DbSession)->TeamService:
    return TeamService(db)
TeamSvc=Annotated[TeamService, Depends(_service)]

@router.get(
    "/{team_id}/members",
    response_model=list[MemberRead],
    summary="Who is in your team",
)
async def list_members(
    team_id:uuid.UUID,
    svc:TeamSvc,
    user:VerifiedUser,
):
    team=await svc.require_team(team_id)
    return await svc.list_members(team)


@router.post(
    "/{team_id}/members",
    response_model=MemberRead,
    status_code=status.HTTP_201_CREATED,
    summary="Ass someone in the team",
      responses={
        400: {"description": "That user cannot be a team member"},
        409: {"description": "Already in this team"},
    },
)
async def add_member(
    team_id:uuid.UUID,
    data:MemberAdd,
    svc:TeamSvc,
    admin:RequireAdmin,
    client:ClientInfo,
):
    team=await svc.require_team(team_id)
    return await svc.add_member(team, data, actor=admin, ip_address=client["ip_address"])

@router.patch(
    "/{team_id}/members/{user_id}",
    response_model=MemberRead,
    summary="Promote or demote a team member"
)
async def set_member_role(
    team_id: uuid.UUID,
    user_id: uuid.UUID,
    data: MemberUpdate,
    svc: TeamSvc,
    admin: RequireAdmin,
    client: ClientInfo,
):
    team= await svc.require_team(team_id)
    return await svc.set_member_role(
        team,
        user_id,
        data.role_in_team,
        actor=admin,
        ip_address=client["ip_address"]
    )
    

@router.delete("/{team_id}/members/{user_id}",
               response_model=dict,
               summary="Remove Someone from the team")
async def remove_member(
    team_id: uuid.UUID,
    user_id: uuid.UUID,
    svc: TeamSvc,
    admin: RequireAdmin,
    client: ClientInfo,
) -> dict:
    team= await svc.require_team(team_id)
    remaining=await svc.remove_member(
        team,
        user_id,
        actor=admin,
        ip_address=client["ip_address"]
    )
    return {"removed":True, "open_tickets_still_assigned":remaining}
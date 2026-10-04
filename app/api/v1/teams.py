import uuid

from fastapi import APIRouter, status

from app.api.deps import ClientInfo, RequireTeamManager, TeamSvc, VerifiedUser
from app.schemas.team import MemberAdd, MemberRead, MemberUpdate

router=APIRouter(prefix="/teams", tags=["Teams"])

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
    summary="Add someone to the team",
      responses={
        400: {"description": "That user cannot be a team member"},
        409: {"description": "Already in this team"},
    },
)
async def add_member(
    team_id:uuid.UUID,
    data:MemberAdd,
    svc:TeamSvc,
    manager:RequireTeamManager,
    client:ClientInfo,
):
    team=await svc.require_team(team_id)
    return await svc.add_member(team, data, actor=manager, ip_address=client["ip_address"])

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
    manager: RequireTeamManager,
    client: ClientInfo,
):
    team= await svc.require_team(team_id)
    return await svc.set_member_role(
        team,
        user_id,
        data.role_in_team,
        actor=manager,
        ip_address=client["ip_address"]
    )


@router.delete("/{team_id}/members/{user_id}",
               response_model=dict,
               summary="Remove Someone from the team")
async def remove_member(
    team_id: uuid.UUID,
    user_id: uuid.UUID,
    svc: TeamSvc,
    manager: RequireTeamManager,
    client: ClientInfo,
) -> dict:
    team= await svc.require_team(team_id)
    remaining=await svc.remove_member(
        team,
        user_id,
        actor=manager,
        ip_address=client["ip_address"]
    )
    return {"removed":True, "open_tickets_still_assigned":remaining}

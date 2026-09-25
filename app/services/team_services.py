import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.exceptions import BadRequest, ConflictError, TeamNotFound, UserNotFound
from app.models.audit import AuditLog
from app.models.enums import TeamRole, TicketStatus, UserRole
from app.models.team import Team, TeamMembership
from app.models.ticket import Ticket
from app.models.user import User
from app.schemas.team import MemberAdd


class TeamService:
    def __init__(self, db:AsyncSession)->None:
        self.db=db
    async def require_team(self, team_id:uuid.UUID)->Team:
        team= await self.db.get(Team, team_id)
        if team is None:
            raise TeamNotFound()
        return team
    async def list_members(self, team:Team)->list[TeamMembership]:
        stmt=(
            select(TeamMembership).where(TeamMembership.team_id == team.id)
            .options(joinedload(TeamMembership.user))
            .order_by(TeamMembership.role_in_team.desc(), TeamMembership.joined_at)
        )
        rows=await self.db.execute(stmt)
        return list(rows.unique().scalars().all())
    
    async def _get_membership(
        self, team:Team, user_id:uuid.UUID
    )->TeamMembership|None:
        return await self.db.get(TeamMembership, (user_id, team.id))
    
    async def add_member(
        self, 
        team:Team,
        data:MemberAdd,
        actor:User,
        *,
        ip_address:str|None=None
    )->TeamMembership:
        user= await self.db.get(User, data.user_id)
        if user is None:
            raise UserNotFound()
        if  not user.is_active:
            raise BadRequest("That account is disabled")
       
        if user.role == UserRole.REQUESTER:
            raise BadRequest(
                "Only agents and administrators can belong to a team."
            )

        if await self._get_membership(team, user.id) is not None:
    
            raise ConflictError(f"{user.full_name} is already in this team.")
        membership = TeamMembership(
            user_id=user.id,
            team_id=team.id,
            role_in_team=data.role_in_team,
        )
        self.db.add(membership)

        self._add_audit(
            actor_id=actor.id,
            team_id=team.id,
            action="member_added",
            changes={
                "user_id": str(user.id),
                "user": user.full_name,
                "role_in_team": data.role_in_team.value,
            },
            ip_address=ip_address,
        )

        await self.db.commit()

      
        refreshed = await self._get_membership(team, user.id)
        assert refreshed is not None  # just committed it
        await self.db.refresh(refreshed, ["user"])
        return refreshed

    async def set_member_role(
        self,
        team: Team,
        user_id: uuid.UUID,
        role: TeamRole,
        actor: User,
        *,
        ip_address: str | None = None,
    ) -> TeamMembership:
        membership = await self._get_membership(team, user_id)
        if membership is None:
            raise UserNotFound("That user is not in this team.")

        if membership.role_in_team == role:
            await self.db.refresh(membership, ["user"])
            return membership

        previous = membership.role_in_team
        membership.role_in_team = role

        self._add_audit(
            actor_id=actor.id,
            team_id=team.id,
            action="member_role_changed",
            changes={
                "user_id": str(user_id),
                "role_in_team": {"from": previous.value, "to": role.value},
            },
            ip_address=ip_address,
        )

        await self.db.commit()
        await self.db.refresh(membership, ["user"])
        return membership

    async def remove_member(
        self,
        team: Team,
        user_id: uuid.UUID,
        actor: User,
        *,
        ip_address: str | None = None,
    ) -> int:

        membership = await self._get_membership(team, user_id)
        if membership is None:
            raise UserNotFound("That user is not in this team.")

        open_tickets = (
            await self.db.scalar(
                select(func.count(Ticket.id)).where(
                    Ticket.assignee_id == user_id,
                    Ticket.team_id == team.id,
                    Ticket.deleted_at.is_(None),
                    Ticket.status.notin_(
                        [TicketStatus.RESOLVED, TicketStatus.CLOSED]
                    ),
                )
            )
            or 0
        )

        self._add_audit(
            actor_id=actor.id,
            team_id=team.id,
            action="member_removed",
            changes={
                "user_id": str(user_id),
                "role_in_team": membership.role_in_team.value,
                "open_tickets_still_assigned": open_tickets,
            },
            ip_address=ip_address,
        )

        await self.db.delete(membership)
        await self.db.commit()
        return open_tickets

    def _add_audit(
        self,
        *,
        actor_id: uuid.UUID | None,
        team_id: uuid.UUID,
        action: str,
        changes: dict[str, Any],
        ip_address: str | None = None,
    ) -> None:
        self.db.add(
            AuditLog(
                actor_id=actor_id,
                entity_type="team",
                entity_id=team_id,
                action=action,
                changes=changes,
                ip_address=ip_address,
            )
        )
        
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Numeric, cast, extract, func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.team import Team
from app.models.ticket import Ticket


class AnalyticsService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def team_sla(self, days: int) -> list[dict[str, Any]]:
        since = datetime.now(UTC) - timedelta(days=days)


        scoped = (
            select(
                Ticket.team_id,
                Ticket.created_at,
                Ticket.resolved_at,
                Ticket.sla_due_at,
                Ticket.sla_breached,
            )
            .where(Ticket.deleted_at.is_(None), Ticket.created_at >= since)
            .cte("scoped")
        )

        hours_to_resolve = extract("epoch", scoped.c.resolved_at - scoped.c.created_at) / 3600

        # CTE 2 "per_team": one row per team.
        per_team = (
            select(
                Team.id.label("team_id"),
                Team.name,
                Team.slug,
                func.count(scoped.c.team_id).label("created"),
                func.count(scoped.c.resolved_at).label("resolved"),
                func.count()
                .filter(scoped.c.resolved_at <= scoped.c.sla_due_at)
                .label("resolved_in_sla"),
                func.count().filter(scoped.c.sla_breached.is_(True)).label("breached"),
                func.percentile_cont(0.5)
                .within_group(hours_to_resolve)
                .label("median_hours"),
            )
          
            .select_from(Team)
            .outerjoin(scoped, scoped.c.team_id == Team.id)
            .group_by(Team.id)
            .cte("per_team")
        )

      
        sla_rate = cast(per_team.c.resolved_in_sla, Numeric) / func.nullif(
            per_team.c.resolved, 0
        )

        stmt = select(
            per_team.c.team_id,
            per_team.c.name,
            per_team.c.slug,
            per_team.c.created,
            per_team.c.resolved,
            per_team.c.breached,
            func.round(cast(per_team.c.median_hours, Numeric), 1).label("median_hours"),
            func.round(100 * sla_rate, 1).label("sla_met_pct"),
           
            
            func.round(
                100
                * cast(per_team.c.created, Numeric)
                / func.nullif(func.sum(per_team.c.created).over(), 0),
                1,
            ).label("share_pct"),
            func.dense_rank()
            .over(order_by=sla_rate.desc().nulls_last())
            .label("sla_rank"),
        ).order_by(literal_column("sla_rank"), per_team.c.name)

        rows = await self.db.execute(stmt)
        # row._mapping = the row as {column name: value}.
        return [dict(row._mapping) for row in rows]
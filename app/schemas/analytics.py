import uuid

from app.schemas.common import APISchema


class TeamSlaStats(APISchema):
    team_id: uuid.UUID
    name: str
    slug: str
    created: int
    resolved: int
    breached: int
    median_hours: float | None  # None = nothing resolved yet
    sla_met_pct: float | None
    share_pct: float | None
    sla_rank: int
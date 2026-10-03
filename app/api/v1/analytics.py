from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.api.deps import DbSession, require_permission
from app.models.enums import Permission
from app.models.user import User
from app.schemas.analytics import TeamSlaStats
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["Analytics"])


Manager = Annotated[User, Depends(require_permission(Permission.TICKET_VIEW_ALL))]


@router.get(
    "/teams",
    response_model=list[TeamSlaStats],
    summary="SLA performance per team",
)
async def team_sla(
    db: DbSession,
    manager: Manager,
    # ge/le: FastAPI rejects 0 or 1000 days with a 422 before our code runs.
    days: Annotated[int, Query(ge=1, le=365)] = 30,
) -> list[dict[str, Any]]:
    return await AnalyticsService(db).team_sla(days)
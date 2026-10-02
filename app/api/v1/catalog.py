from typing import Any

from fastapi import APIRouter
from pydantic import TypeAdapter
from sqlalchemy import select

from app.api.deps import DbSession, VerifiedUser
from app.core.cache import CATALOG_TTL_SECONDS, CATEGORIES_KEY, TEAMS_KEY, get_or_load
from app.models.team import Category, Team
from app.schemas.ticket import CategoryBrief, TeamBrief

router = APIRouter(tags=["Catalog"])

_categories = TypeAdapter(list[CategoryBrief])
_teams = TypeAdapter(list[TeamBrief])

@router.get(
    "/categories",
    response_model=list[CategoryBrief],
    summary="List ticket Categories",
)
async def list_categories(db: DbSession, user: VerifiedUser) -> Any:
    async def load() -> Any:
        rows = (await db.scalars(select(Category).order_by(Category.name))).all()
        return _categories.dump_python(_categories.validate_python(rows), mode="json")

    return await get_or_load(CATEGORIES_KEY, CATALOG_TTL_SECONDS, load)


@router.get("/teams", response_model=list[TeamBrief], summary="List teams")
async def list_teams(db: DbSession, user: VerifiedUser) -> Any:
    async def load() -> Any:
        rows = (await db.scalars(select(Team).order_by(Team.name))).all()
        return _teams.dump_python(_teams.validate_python(rows), mode="json")

    return await get_or_load(TEAMS_KEY, CATALOG_TTL_SECONDS, load)
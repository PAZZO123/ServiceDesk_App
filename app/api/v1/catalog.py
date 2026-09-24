from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DbSession, VerifiedUser
from app.models.team import Category, Team
from app.schemas.ticket import CategoryBrief, TeamBrief

router=APIRouter(tags=["Catalog"])

@router.get(
    "/categories",
    response_model=list[CategoryBrief],
    summary="List ticket Categories"
)
async def list_categories(db: DbSession, user:VerifiedUser)->list[Category]:
    result=await db.execute(select(Category).order_by(Category.name))
    return list(result.scalars().all())

@router.get("/teams", response_model=list[TeamBrief], summary="List teams")
async def list_teams(db:DbSession, user:VerifiedUser)->list[Team]:
    result= await db.execute(select(Team).order_by(Team.name))
    return list(result.scalars().all())


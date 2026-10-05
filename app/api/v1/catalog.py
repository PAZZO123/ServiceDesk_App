from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from pydantic import TypeAdapter
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import ClientInfo, DbSession, VerifiedUser, require_permission
from app.core.cache import CATALOG_TTL_SECONDS, CATEGORIES_KEY, TEAMS_KEY, get_or_load
from app.core.exceptions import TagAlreadyExists
from app.models.enums import Permission
from app.models.tag import Tag
from app.models.team import Category, Team
from app.models.user import User
from app.schemas.ticket import CategoryBrief, TagBrief, TagCreate, TeamBrief
from app.services.audit import add_audit

router = APIRouter(tags=["Catalog"])

_categories = TypeAdapter(list[CategoryBrief])
_teams = TypeAdapter(list[TeamBrief])

# The people who tag tickets (PUT /tickets/{id}/tags) may also create tags.
Staff = Annotated[User, Depends(require_permission(Permission.TICKET_WORK))]


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

@router.get("/tags", response_model=list[TagBrief], summary="List tags")
async def list_tags(db: DbSession, user:VerifiedUser)->Any:
    return (await db.scalars(select(Tag).order_by(Tag.name))).all()


@router.post(
    "/tags",
    response_model=TagBrief,
    status_code=status.HTTP_201_CREATED,
    summary="Create a tag",
    responses={
        403: {"description": "Only support staff create tags"},
        409: {"description": "A tag with this name already exists"},
    },
)
async def create_tag(
    data: TagCreate, db: DbSession, staff: Staff, client: ClientInfo
) -> Tag:
    # Friendly check first: the normal case gets a clear 409...
    if await db.scalar(select(Tag.id).where(Tag.name == data.name)):
        raise TagAlreadyExists()

    tag = Tag(name=data.name, color=data.color)
    db.add(tag)
    try:
        await db.flush()
    except IntegrityError as exc:
        # ...and the unique index (ix_tags_name) catches two people creating
        # the same tag at the same moment: still a 409, never a 500.
        await db.rollback()
        raise TagAlreadyExists() from exc

    add_audit(
        db,
        actor_id=staff.id,
        entity_type="tag",
        entity_id=tag.id,
        action="tag_created",
        changes={"name": tag.name, "color": tag.color},
        ip_address=client["ip_address"],
    )
    await db.commit()
    return tag

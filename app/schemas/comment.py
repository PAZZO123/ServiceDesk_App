import uuid
from datetime import datetime

from pydantic import Field, computed_field

from app.schemas.common import APISchema
from app.schemas.user import UserPublic


class CommentCreate(APISchema):
    body:str=Field(
        min_length=1,
        max_length=10000,
        description="the comment text"
    )
    is_internal:bool=Field(
        default=False,
        description=("Staff Only . An internal note is never shown to the person who raised the tickted")
    )


class CommentUpdate(APISchema):
    body:str=Field(min_length=1, max_length=10000)


class CommentRead(APISchema):
    id:uuid.UUID
    ticket_id:uuid.UUID
    body:str
    is_internal:bool
    author:UserPublic
    created_at:datetime
    updated_at:datetime

    @computed_field  # type: ignore[misc, prop-decorator]
    @property
    def edited(self)->bool:
        return self.updated_at > self.created_at

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from fastapi import Query
from pydantic import Field, field_validator, model_validator

from app.models.enums import TicketPriority, TicketStatus
from app.schemas.common import APISchema
from app.schemas.user import UserPublic

#small nested piece

class TeamBrief(APISchema):
    id:uuid.UUID
    name:str
    slug:str
    
class CategoryBrief(APISchema):
    id:uuid.UUID
    name:str
    sla_hours:int
    
#INPUT
class TicketCreate(APISchema):
    title: str= Field(
        min_length=5,
        max_length=200,
        description="A short summary of the problem"
    )
    description:str=Field(
        min_length=10,
        max_length=10_000,
        description="What happened , what you expected, what you tried"
    )
    category_id: uuid.UUID=Field(
        description="Chosen from Get / categories. Determines the team and SLA."
    )
    priority:TicketPriority =Field(
        default=TicketPriority.MEDIUM,
        description="How urgent is this."
    )
    extra_data: dict[str, Any]=Field(
        default_factory=dict,
        description="Optional category-specific fields."
    )
    @field_validator("title", "description")
    @classmethod
    def not_only_whitespaces(cls, v:str)->str:
        if not v.strip():
            raise ValueError("This field can not be empty")
        return v

class TicketUpdate(APISchema):
    title: str | None = Field(default=None, min_length=5, max_length=200)
    description: str | None = Field(default=None, min_length=10, max_length=10_000)
    priority: TicketPriority | None = None
    category_id: uuid.UUID | None = None
    extra_data: dict[str, Any] | None = None
    
class TagBrief(APISchema):
    id: uuid.UUID
    name: str
    color: str
    
class StatusChange(APISchema):
    status: TicketStatus
    comment:str|None=Field(
        default=None,
        max_length=1000,
        description="Optional note explaining the change"
    )
class AssignRequest(APISchema):
    assignee_id: uuid.UUID | None = Field(
        default=None,
        description="Who should own this ticket. Send null to unassign.",
    )


class TagsUpdate(APISchema):
    tag_ids: list[uuid.UUID] = Field(
        default_factory=list,
        max_length=10,
        description=(
            "The complete set of tags for this ticket. "
            "This REPLACES the current tags - send the full list every time."
        ),
    )
    
class TicketListItem(APISchema):
    id: uuid.UUID
    reference: str
    title: str
    status: TicketStatus
    priority: TicketPriority
    created_at: datetime
    updated_at: datetime
    sla_due_at: datetime
    sla_breached: bool

    requester: UserPublic
    assignee: UserPublic | None = None
    category: CategoryBrief
    team: TeamBrief
    tags: list[TagBrief] = Field(default_factory=list)
    
class TicketRead(TicketListItem):
    description: str
    extra_data: dict[str, Any]

    first_response_at: datetime | None = None
    resolved_at: datetime | None = None
    closed_at: datetime | None = None

    merged_into_id: uuid.UUID | None = None
    
#Filtering and Sorting
class TicketSortField(StrEnum):
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
    PRIORITY = "priority"
    SLA_DUE_AT = "sla_due_at"
    STATUS = "status"
    
class SortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"
    

    
class TicketFilters(APISchema):
    status: TicketStatus | None = Query(
        default=None, description="Only tickets in this state."
    )
    priority: TicketPriority | None = Query(default=None)
    category_id: uuid.UUID | None = Query(default=None)
    team_id: uuid.UUID | None = Query(default=None)
    assignee_id: uuid.UUID | None = Query(
        default=None, description="Tickets owned by this agent."
    )
    requester_id: uuid.UUID | None = Query(default=None)

    unassigned: bool | None = Query(
        default=None,
        description="True returns only tickets with no assignee.",
    )
    sla_breached: bool | None = Query(default=None)

    created_after: datetime | None = Query(default=None)
    created_before: datetime | None = Query(default=None)
    q: str | None = Query(
        default=None,
        min_length=2,
        max_length=100,
        description="Search the title and description.",
    )
    sort: TicketSortField = Query(default=TicketSortField.CREATED_AT)
    order: SortOrder = Query(default=SortOrder.DESC)
    
    @model_validator(mode="after")
    def dates_must_be_ordered(self) -> "TicketFilters":
        """Reject a range that cannot contain anything."""
        if (
            self.created_after is not None
            and self.created_before is not None
            and self.created_after > self.created_before
        ):
            raise ValueError("created_after must be earlier than created_before.")
        return self
    @property
    def has_date_range(self) ->bool:
        return self.created_after is not None or self.created_before is not None
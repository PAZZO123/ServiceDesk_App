import uuid
from datetime import datetime
from typing import Any

from app.models.enums import NotificationType
from app.schemas.common import APISchema


class NotificationRead(APISchema):
    id:uuid.UUID
    type:NotificationType
    payload:dict[str, Any]
    read_at:datetime| None
    created_at:datetime
    
class UnreadCount(APISchema):
    unread:int
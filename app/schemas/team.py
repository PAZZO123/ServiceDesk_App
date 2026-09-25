import uuid
from datetime import datetime

from app.models.enums import TeamRole
from app.schemas.common import APISchema
from app.schemas.user import UserPublic


class MemberRead(APISchema):
    user:UserPublic
    role_in_team:TeamRole
    joined_at:datetime
    

class MemberAdd(APISchema):
    user_id:uuid.UUID
    role_in_team:TeamRole=TeamRole.MEMBER
    
class MemberUpdate(APISchema):
    role_in_team:TeamRole
import uuid
from datetime import datetime

from pydantic import computed_field

from app.core.config import settings
from app.schemas.common import APISchema
from app.schemas.user import UserPublic


class AttachmentRead(APISchema):
    id: uuid.UUID
    ticket_id: uuid.UUID | None = None
    comment_id: uuid.UUID | None = None

    original_filename: str
    content_type: str
    size_bytes: int
    created_at: datetime
    uploader: UserPublic

    @computed_field  
    @property
    def download_url(self) -> str:
        return f"{settings.API_V1_PREFIX}/attachments/{self.id}/download"

    @computed_field  # type: ignore[misc, prop-decorator]
    @property
    def size_human(self) -> str:
        size = float(self.size_bytes)
        for unit in ("B", "KB", "MB"):
            if size < 1024 or unit == "MB":
                return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} MB"
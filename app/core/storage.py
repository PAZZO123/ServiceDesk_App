import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

import aiofiles
import magic
from fastapi import UploadFile

from app.core.config import settings
from app.core.exceptions import FileTooLarge, UnsupportedFileType

CHUNK_SIZE=64*1024
ALLOWED_MIME_TYPES:dict[str, str]={
    "image/png":".png",
    "image/jpeg":".jpg",
    "image/gif":".gif",
    "image/webp":".webp",
    "application/pdf":".pdf",
    "text/plain":".txt",
    "text/csv":".csv",
    "application/zip":".zip",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx"
    
}

def build_relative_path(extension:str)->str:
    today=datetime.now(UTC)
    return f"{today:%Y/%m/%d}/{uuid.uuid4().hex}{extension}"

def absolute_path(relative:str) ->Path:
    root = settings.UPLOAD_DIR.resolve()
    full=(root/relative).resolve()
    if not full.is_relative_to(root):
        raise UnsupportedFileType("Invalide storage path.")
    return full

def safe_header_filename(name:str)->str:
    cleaned = name.replace("\r", "").replace("\n", "").replace('"', "")
    cleaned = cleaned.replace("\\", "/")
    return PurePosixPath(cleaned).name or "download"

async def save_upload(upload:UploadFile, max_bytes:int)->tuple[str, str, str]:
    first_chunk= await upload.read(CHUNK_SIZE)
    if not first_chunk:
        raise UnsupportedFileType("The file is empty")
    detected=magic.from_buffer(first_chunk, mime=True)
    if detected not in ALLOWED_MIME_TYPES:
        raise UnsupportedFileType(f"Files of type {detected} are not accepted.")
    
    relative=build_relative_path(ALLOWED_MIME_TYPES[detected])
    destination=absolute_path(relative)
    destination.parent.mkdir(parents=True, exist_ok=True)
    
    size=0
    chunk=first_chunk
    try:
        async with aiofiles.open(destination, "wb") as out:
            while chunk:
                size+=len(chunk)
                if size > max_bytes:
                    raise FileTooLarge(
                        f"Files must be smaller than {settings.MAX_UPLOAD_MB} MB."
                    )

                await out.write(chunk)
                chunk = await upload.read(CHUNK_SIZE)

    except Exception:
    
        destination.unlink(missing_ok=True)
        raise

    return relative, detected, size


async def stream_file(relative: str) -> AsyncIterator[bytes]:
    path = absolute_path(relative)

    async with aiofiles.open(path, "rb") as handle:
        while chunk := await handle.read(CHUNK_SIZE):
            yield chunk


def delete_file(relative: str) -> None:
    absolute_path(relative).unlink(missing_ok=True)
import asyncio
import logging
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.attachment import Attachment
from app.workers.celery_app import celery_app
from app.workers.db import worker_session

logger = logging.getLogger(__name__)

OUR_FILE = re.compile(r"^[0-9a-f]{32}\.[a-z0-9]+$")


MIN_AGE = timedelta(hours=1)

CHUNK = 500


def _old_candidates(root: Path, cutoff: datetime) -> list[str]:
    found = []
    for path in root.rglob("*"):
        if not path.is_file() or not OUR_FILE.match(path.name):
            continue
        modified = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
        if modified < cutoff:
            found.append(path.relative_to(root).as_posix())
    return found


async def sweep_orphan_files(
    db: AsyncSession, root: Path | None = None, now: datetime | None = None
) -> list[str]:
    root = (root or settings.UPLOAD_DIR).resolve()
    if not root.is_dir():
        return []
    cutoff = (now or datetime.now(UTC)) - MIN_AGE

    candidates = _old_candidates(root, cutoff)

    known: set[str] = set()
    for start in range(0, len(candidates), CHUNK):
        chunk = candidates[start : start + CHUNK]
        rows = await db.scalars(
            select(Attachment.storage_path).where(Attachment.storage_path.in_(chunk))
        )
        known.update(rows)

    deleted = []
    for relative in candidates:
        if relative in known:
            continue
        (root / relative).unlink(missing_ok=True)
        deleted.append(relative)
    return deleted


async def _run_sweep() -> list[str]:
    async with worker_session() as db:
        return await sweep_orphan_files(db)


@celery_app.task(name="files.sweep_orphans")
def sweep_orphan_files_task() -> int:
    deleted = asyncio.run(_run_sweep())
    for relative in deleted:
        logger.warning("orphan_file_deleted path=%s", relative)
    return len(deleted)
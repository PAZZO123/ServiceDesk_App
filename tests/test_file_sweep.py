import os
import time
from pathlib import Path

import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.team import Category
from app.workers.file_tasks import sweep_orphan_files
from tests.conftest import MakeUser, auth
from tests.test_attachments import TINY_PNG

TWO_HOURS_AGO = time.time() - 2 * 3600


@pytest.fixture
def root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path)
    return tmp_path


def put(root: Path, relative: str, old: bool) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")
    if old:
        # os.utime sets the "last modified" time - the clock the sweep
        # reads. Faster than waiting an hour in a test.
        os.utime(path, (TWO_HOURS_AGO, TWO_HOURS_AGO))
    return path


async def sweep(root: Path) -> list[str]:
    async with AsyncSessionLocal() as db:
        return await sweep_orphan_files(db, root)


async def test_old_orphan_is_deleted(root: Path) -> None:
    orphan = put(root, "2026/09/01/" + "a" * 32 + ".pdf", old=True)

    assert await sweep(root) == ["2026/09/01/" + "a" * 32 + ".pdf"]
    assert not orphan.exists()


async def test_recent_orphan_is_kept(root: Path) -> None:
    recent = put(root, "2026/10/02/" + "b" * 32 + ".png", old=False)

    assert await sweep(root) == []
    assert recent.exists()


async def test_files_we_did_not_write_are_never_touched(root: Path) -> None:
    keep = [
        put(root, ".gitkeep", old=True),
        put(root, "README.txt", old=True),
        put(root, "2026/09/01/holiday-photo.jpg", old=True),
    ]
    assert await sweep(root) == []
    assert all(p.exists() for p in keep)


async def test_file_with_a_row_is_kept(
    client: AsyncClient,
    make_user: MakeUser,
    categories: dict[str, Category],
    root: Path,
) -> None:
    # A REAL upload through the API: file on disk + row in attachments.
    user = await make_user("requester")
    r = await client.post(
        "/api/v1/tickets",
        headers=auth(user),
        json={
            "title": "Screen flickers",
            "description": "Since this morning.",
            "category_id": str(categories["network"].id),
        },
    )
    assert r.status_code == 201, r.text
    r = await client.post(
        f"/api/v1/tickets/{r.json()['id']}/attachments",
        headers=auth(user),
        files={"file": ("screen.png", TINY_PNG, "image/png")},
    )
    assert r.status_code == 201, r.text

    # Make the real file look old, so ONLY the row protects it.
    (stored,) = [p for p in root.rglob("*") if p.is_file()]
    os.utime(stored, (TWO_HOURS_AGO, TWO_HOURS_AGO))

    assert await sweep(root) == []
    assert stored.exists()


async def test_missing_upload_folder_is_not_an_error(tmp_path: Path) -> None:
    async with AsyncSessionLocal() as db:
        assert await sweep_orphan_files(db, tmp_path / "does-not-exist") == []
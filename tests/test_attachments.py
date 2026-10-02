
import base64
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.audit import AuditLog
from app.models.team import Category, Team
from tests.conftest import MakeUser, auth

TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


@pytest.fixture(autouse=True)
def uploads_in_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path)


async def test_deleting_comment_attachment_is_audited_on_the_ticket(
    client: AsyncClient,
    make_user: MakeUser,
    teams: dict[str, Team],
    categories: dict[str, Category],
) -> None:
    requester = await make_user("requester")
    agent = await make_user("agent", team=teams["network"])

    r = await client.post(
        "/api/v1/tickets",
        headers=auth(requester),
        json={
            "title": "Printer jam",
            "description": "Paper stuck in tray 2.",
            "category_id": str(categories["network"].id),
        },
    )
    assert r.status_code == 201, r.text
    ticket_id = r.json()["id"]

    r = await client.post(
        f"/api/v1/tickets/{ticket_id}/comments",
        headers=auth(agent),
        json={"body": "Photo of the error screen attached."},
    )
    assert r.status_code == 201, r.text
    comment_id = r.json()["id"]

    # files= sends multipart/form-data, like a browser <input type="file">.
    # The key "file" must match the parameter name in the route.
    r = await client.post(
        f"/api/v1/comments/{comment_id}/attachments",
        headers=auth(agent),
        files={"file": ("screen.png", TINY_PNG, "image/png")},
    )
    assert r.status_code == 201, r.text
    attachment_id = r.json()["id"]

    r = await client.delete(f"/api/v1/attachments/{attachment_id}", headers=auth(agent))
    assert r.status_code == 204, r.text

    # Look at the audit row directly in the database: there is no API
    # endpoint for the audit log, and this is exactly what it stores.
    async with AsyncSessionLocal() as db:
        row = await db.scalar(
            select(AuditLog).where(AuditLog.action == "attachment_removed")
        )
    assert row is not None
    assert row.entity_type == "ticket"
    assert str(row.entity_id) == ticket_id  # the bug: this was comment_id

import asyncio
import os
import subprocess
import sys
from pathlib import Path

import jwt
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.config import Settings, settings
from app.core.security import create_access_token
from app.db.session import AsyncSessionLocal
from app.models.audit import AuditLog
from app.models.tag import Tag
from app.models.team import Category, Team
from tests.conftest import MakeUser, auth

ROOT = Path(__file__).resolve().parents[1]


def lock_key_in_new_process(hash_seed: str) -> int:
    code = "from app.services.ticket_service import reference_lock_key; print(reference_lock_key(2026))"
    env = {**os.environ, "PYTHONHASHSEED": hash_seed}
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True, check=True)
    return int(out.stdout.strip().splitlines()[-1])


def test_reference_lock_key_is_the_same_in_every_process() -> None:
    assert lock_key_in_new_process("1") == lock_key_in_new_process("2")


async def test_parallel_creates_get_unique_references(
    client: AsyncClient, make_user: MakeUser, categories: dict[str, Category]
) -> None:
    user = await make_user("requester")

    async def create(i: int) -> str:
        r = await client.post(
            "/api/v1/tickets",
            headers=auth(user),
            json={
                "title": f"Parallel ticket {i}",
                "description": "Created at the same time as the others.",
                "category_id": str(categories["network"].id),
            },
        )
        assert r.status_code == 201, r.text
        return r.json()["reference"]

    references = await asyncio.gather(*(create(i) for i in range(20)))
    assert len(set(references)) == 20


def test_access_token_lifetime_comes_from_the_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "7")
    assert Settings().ACCESS_TOKEN_EXPIRE_MINUTES == 7  # type: ignore[call-arg]


def test_access_token_has_no_role_claim() -> None:
    token = create_access_token("00000000-0000-0000-0000-000000000001")
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    assert "role" not in payload
    assert payload["exp"] - payload["iat"] == pytest.approx(settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60, abs=1)


async def test_feed_refuses_a_sort_it_cannot_honour(client: AsyncClient, make_user: MakeUser) -> None:
    headers = auth(await make_user("requester"))
    r = await client.get("/api/v1/tickets/feed", headers=headers, params={"sort": "priority"})
    assert r.status_code == 400, r.text
    r = await client.get("/api/v1/tickets/feed", headers=headers)
    assert r.status_code == 200, r.text
    assert set(r.json()) == {"items", "next_cursor", "has_more"}
    

async def test_tags_lists_every_tag_a_to_z(client: AsyncClient, make_user: MakeUser) -> None:
    # GET /tags: the full list, even tags that no ticket uses yet.
    # Inserted directly (POST /tags exists since 2026-10-05, tested in
    # test_tags_and_deletes.py); this test is only about the listing.
    async with AsyncSessionLocal() as db:
        db.add_all([Tag(name="vpn", color="#2563EB"), Tag(name="hardware")])
        await db.commit()
    r = await client.get("/api/v1/tags", headers=auth(await make_user("requester")))
    assert r.status_code == 200, r.text
    assert [t["name"] for t in r.json()] == ["hardware", "vpn"]
    assert r.json()[1]["color"] == "#2563EB"


async def test_tags_needs_a_signed_in_user(client: AsyncClient) -> None:
    r = await client.get("/api/v1/tags")
    assert r.status_code == 401, r.text


async def test_shared_audit_helper_still_records_team_changes(
    client: AsyncClient, make_user: MakeUser, teams: dict[str, Team]
) -> None:
    # The three private _add_audit copies were replaced by services/audit.py.
    # A team change must still write a row with entity_type "team".
    admin = await make_user("admin")
    agent = await make_user("agent")
    team_id = teams["network"].id
    r = await client.post(
        f"/api/v1/teams/{team_id}/members", headers=auth(admin), json={"user_id": str(agent.id)}
    )
    assert r.status_code == 201, r.text
    async with AsyncSessionLocal() as db:
        row = (await db.scalars(select(AuditLog).where(AuditLog.action == "member_added"))).one()
    assert (row.entity_type, row.entity_id, row.actor_id) == ("team", team_id, admin.id)
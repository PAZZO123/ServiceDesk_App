
import csv
import io
from dataclasses import dataclass

import pytest
from httpx import AsyncClient

from app.models.team import Category, Team
from app.models.user import User
from tests.conftest import MakeUser, auth


@dataclass
class World:
    users: dict[str, User]  
    ticket_id: str  


ACTORS = [
    "owner",  
    "stranger", 
    "agent_in",  
    "agent_out", 
    "observer",
    "admin",  
    
]


@pytest.fixture
async def world(
    client: AsyncClient,
    make_user: MakeUser,
    teams: dict[str, Team],
    categories: dict[str, Category],
) -> World:
    users = {
        "owner": await make_user("requester", email="owner@example.com"),
        "stranger": await make_user("requester", email="stranger@example.com"),
        "agent_in": await make_user(
            "agent", email="in@example.com", team=teams["network"]
        ),
        "agent_out": await make_user(
            "agent", email="out@example.com", team=teams["accounts"]
        ),
        "observer": await make_user("observer"),
        "admin": await make_user("admin"),
    }

    r = await client.post(
        "/api/v1/tickets",
        headers=auth(users["owner"]),
        json={
            "title": "Wi-Fi is down",
            "description": "No Wi-Fi on floor 2 since 9 am.",
            "category_id": str(categories["network"].id),
        },
    )
    assert r.status_code == 201, r.text
    ticket_id = r.json()["id"]

    for body, internal in [("We are on it.", False), ("Router 2B is dead.", True)]:
        r = await client.post(
            f"/api/v1/tickets/{ticket_id}/comments",
            headers=auth(users["agent_in"]),
            json={"body": body, "is_internal": internal},
        )
        assert r.status_code == 201, r.text

    return World(users=users, ticket_id=ticket_id)


VIEW = [
    ("owner", 200),
    ("stranger", 404),
    ("agent_in", 200),
    ("agent_out", 404),
    ("observer", 200),
    ("admin", 200),
]


@pytest.mark.parametrize(("actor", "expected"), VIEW)
async def test_view_one_ticket(
    client: AsyncClient, world: World, actor: str, expected: int
) -> None:
    r = await client.get(
        f"/api/v1/tickets/{world.ticket_id}", headers=auth(world.users[actor])
    )
    assert r.status_code == expected, r.text


@pytest.mark.parametrize("actor", ACTORS)
async def test_list_agrees_with_detail(
    client: AsyncClient, world: World, actor: str
) -> None:
    headers = auth(world.users[actor])

    listed = await client.get("/api/v1/tickets", headers=headers)
    assert listed.status_code == 200, listed.text
    ids_in_list = {t["id"] for t in listed.json()["items"]}

    detail = await client.get(f"/api/v1/tickets/{world.ticket_id}", headers=headers)

    in_list = world.ticket_id in ids_in_list
    can_open = detail.status_code == 200
    assert in_list == can_open, (
        f"{actor}: list says {in_list}, detail says {can_open} - "
        "visibility_conditions() and can_view() disagree"
    )


# ---- 3. The CSV export uses the SQL half too ------------------------------
EXPORT_ROWS = [
    ("owner", 1),
    ("stranger", 0),
    ("agent_in", 1),
    ("agent_out", 0),
    ("observer", 1),
    ("admin", 1),
]


@pytest.mark.parametrize(("actor", "rows"), EXPORT_ROWS)
async def test_export_only_contains_visible_tickets(
    client: AsyncClient, world: World, actor: str, rows: int
) -> None:
    r = await client.get("/api/v1/exports/tickets.csv", headers=auth(world.users[actor]))
    assert r.status_code == 200, r.text
    lines = list(csv.reader(io.StringIO(r.text)))
    assert len(lines) - 1 == rows  # -1 for the header row



COMMENT = [
    ("owner", 201),
    ("stranger", 404),  
    ("agent_in", 201),
    ("agent_out", 404),
    ("observer", 403),  
    ("admin", 201),
]


@pytest.mark.parametrize(("actor", "expected"), COMMENT)
async def test_post_public_comment(
    client: AsyncClient, world: World, actor: str, expected: int
) -> None:
    r = await client.post(
        f"/api/v1/tickets/{world.ticket_id}/comments",
        headers=auth(world.users[actor]),
        json={"body": "Any news?"},
    )
    assert r.status_code == expected, r.text


async def test_requester_cannot_write_internal_note(
    client: AsyncClient, world: World
) -> None:
    r = await client.post(
        f"/api/v1/tickets/{world.ticket_id}/comments",
        headers=auth(world.users["owner"]),
        json={"body": "Let me sneak a note in.", "is_internal": True},
    )
    assert r.status_code == 403, r.text


READ_COMMENTS = [
    ("owner", 1), 
    ("agent_in", 2),
    ("observer", 2), 
    ("admin", 2),
]


@pytest.mark.parametrize(("actor", "visible"), READ_COMMENTS)
async def test_internal_notes_hidden_from_requester(
    client: AsyncClient, world: World, actor: str, visible: int
) -> None:
    r = await client.get(
        f"/api/v1/tickets/{world.ticket_id}/comments",
        headers=auth(world.users[actor]),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["items"]) == visible
    assert body["total"] == visible

STATUS = [
    ("owner", "closed", 200), 
    ("owner", "in_progress", 403),  
    ("stranger", "closed", 404),
    ("agent_in", "in_progress", 200),
    ("agent_out", "in_progress", 404),
    ("observer", "in_progress", 403),
    ("admin", "in_progress", 200),
]


@pytest.mark.parametrize(("actor", "new_status", "expected"), STATUS)
async def test_change_status(
    client: AsyncClient, world: World, actor: str, new_status: str, expected: int
) -> None:
    r = await client.post(
        f"/api/v1/tickets/{world.ticket_id}/status",
        headers=auth(world.users[actor]),
        json={"status": new_status},
    )
    assert r.status_code == expected
DELETE = [
    ("owner", 403),
    ("stranger", 404),
    ("agent_in", 403),
    ("agent_out", 404),
    ("observer", 403),
    ("admin", 204),
]


@pytest.mark.parametrize(("actor", "expected"), DELETE)
async def test_delete_ticket(
    client: AsyncClient, world: World, actor: str, expected: int
) -> None:
    r = await client.delete(
        f"/api/v1/tickets/{world.ticket_id}", headers=auth(world.users[actor])
    )
    assert r.status_code == expected, r.text


# Unverified accounts are stopped at the door 
async def test_unverified_user_is_refused(
    client: AsyncClient, make_user: MakeUser
) -> None:
    user = await make_user("agent", verified=False)
    r = await client.get("/api/v1/tickets", headers=auth(user))
    assert r.status_code == 403, r.text
    
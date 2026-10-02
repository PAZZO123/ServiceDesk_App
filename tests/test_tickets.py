import asyncio
import json
from datetime import datetime, timedelta

import asyncpg
from httpx import AsyncClient
from sqlalchemy import select

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.audit import Notification
from app.models.tag import Tag
from app.models.team import Category, Team
from app.models.user import User
from app.realtime.events import TICKET_CHANNEL, team_room
from tests.conftest import MakeUser, auth


async def new_ticket(
    client: AsyncClient, user: User, category: Category, title: str = "Printer is jammed"
) -> dict:
    r = await client.post(
        "/api/v1/tickets",
        headers=auth(user),
        json={
            "title": title,
            "description": "Paper stuck in tray 2 again.",
            "category_id": str(category.id),
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


# Editing 
async def test_requester_edits_title_while_open(
    client: AsyncClient, make_user: MakeUser, categories: dict[str, Category]
) -> None:
    owner = await make_user("requester")
    t = await new_ticket(client, owner, categories["network"])
    r = await client.patch(
        f"/api/v1/tickets/{t['id']}", headers=auth(owner), json={"title": "Printer jammed on floor 2"}
    )
    assert r.status_code == 200, r.text
    assert r.json()["title"] == "Printer jammed on floor 2"


async def test_requester_cannot_change_priority(
    client: AsyncClient, make_user: MakeUser, categories: dict[str, Category]
) -> None:
    # Requesters may only edit title, description, extra_data.
    owner = await make_user("requester")
    t = await new_ticket(client, owner, categories["network"])
    r = await client.patch(
        f"/api/v1/tickets/{t['id']}", headers=auth(owner), json={"priority": "urgent"}
    )
    assert r.status_code == 403, r.text


async def test_requester_cannot_edit_after_resolution(
    client: AsyncClient, make_user: MakeUser, teams: dict[str, Team], categories: dict[str, Category]
) -> None:
    owner = await make_user("requester")
    agent = await make_user("agent", team=teams["network"])
    t = await new_ticket(client, owner, categories["network"])
    r = await client.post(
        f"/api/v1/tickets/{t['id']}/status", headers=auth(agent), json={"status": "resolved"}
    )
    assert r.status_code == 200, r.text
    assert r.json()["resolved_at"] is not None  # stamped on the way to resolved
    r = await client.patch(
        f"/api/v1/tickets/{t['id']}", headers=auth(owner), json={"title": "Still jammed, sorry"}
    )
    assert r.status_code == 403, r.text


# Status 
async def test_closed_ticket_cannot_be_reopened(
    client: AsyncClient, make_user: MakeUser, teams: dict[str, Team], categories: dict[str, Category]
) -> None:
    # ALLOWED_TRANSITIONS[CLOSED] is empty: even staff get 409, because
    # the rule is about the ticket's state, not about who is asking.
    owner = await make_user("requester")
    agent = await make_user("agent", team=teams["network"])
    t = await new_ticket(client, owner, categories["network"])
    r = await client.post(
        f"/api/v1/tickets/{t['id']}/status", headers=auth(owner), json={"status": "closed"}
    )
    assert r.status_code == 200, r.text
    r = await client.post(
        f"/api/v1/tickets/{t['id']}/status", headers=auth(agent), json={"status": "in_progress"}
    )
    assert r.status_code == 409, r.text


async def test_status_change_with_comment_adds_the_comment(
    client: AsyncClient, make_user: MakeUser, teams: dict[str, Team], categories: dict[str, Category]
) -> None:
    owner = await make_user("requester")
    agent = await make_user("agent", team=teams["network"])
    t = await new_ticket(client, owner, categories["network"])
    r = await client.post(
        f"/api/v1/tickets/{t['id']}/status",
        headers=auth(agent),
        json={"status": "waiting", "comment": "Waiting for a new toner cartridge."},
    )
    assert r.status_code == 200, r.text
    r = await client.get(f"/api/v1/tickets/{t['id']}/comments", headers=auth(owner))
    assert [c["body"] for c in r.json()["items"]] == ["Waiting for a new toner cartridge."]


#  Assignment and tags 
async def test_claim_and_assign_follow_team_rules(
    client: AsyncClient, make_user: MakeUser, teams: dict[str, Team], categories: dict[str, Category]
) -> None:
    owner = await make_user("requester")
    agent = await make_user("agent", email="in@example.com", team=teams["network"])
    outsider = await make_user("agent", email="out@example.com", team=teams["accounts"])
    t = await new_ticket(client, owner, categories["network"])

    r = await client.post(f"/api/v1/tickets/{t['id']}/claim", headers=auth(agent))
    assert r.status_code == 200, r.text
    assert r.json()["assignee"]["id"] == str(agent.id)

    # Staff, but not in the ticket's team -> 400.
    r = await client.post(
        f"/api/v1/tickets/{t['id']}/assign",
        headers=auth(agent),
        json={"assignee_id": str(outsider.id)},
    )
    assert r.status_code == 400, r.text

    # Not staff at all -> 400.
    r = await client.post(
        f"/api/v1/tickets/{t['id']}/assign",
        headers=auth(agent),
        json={"assignee_id": str(owner.id)},
    )
    assert r.status_code == 400, r.text

    # null = unassign.
    r = await client.post(
        f"/api/v1/tickets/{t['id']}/assign", headers=auth(agent), json={"assignee_id": None}
    )
    assert r.status_code == 200, r.text
    assert r.json()["assignee"] is None


async def test_tags_replace_the_whole_set(
    client: AsyncClient, make_user: MakeUser, teams: dict[str, Team], categories: dict[str, Category]
) -> None:
    owner = await make_user("requester")
    agent = await make_user("agent", team=teams["network"])
    t = await new_ticket(client, owner, categories["network"])
    # There is no API to create tags, so the test inserts them directly.
    async with AsyncSessionLocal() as db:
        urgent, floor2 = Tag(name="urgent"), Tag(name="floor-2")
        db.add_all([urgent, floor2])
        await db.commit()

    r = await client.put(
        f"/api/v1/tickets/{t['id']}/tags",
        headers=auth(agent),
        json={"tag_ids": [str(urgent.id), str(floor2.id)]},
    )
    assert r.status_code == 200, r.text
    assert {tag["name"] for tag in r.json()["tags"]} == {"urgent", "floor-2"}

    # PUT replaces: sending one tag removes the other.
    r = await client.put(
        f"/api/v1/tickets/{t['id']}/tags", headers=auth(agent), json={"tag_ids": [str(floor2.id)]}
    )
    assert {tag["name"] for tag in r.json()["tags"]} == {"floor-2"}


# Cursor pagination 
async def test_feed_cursor_walks_every_ticket_once(
    client: AsyncClient, make_user: MakeUser, categories: dict[str, Category]
) -> None:
    owner = await make_user("requester")
    created = [
        (await new_ticket(client, owner, categories["network"], f"Ticket number {i}"))["id"]
        for i in range(5)
    ]

    seen: list[str] = []
    cursor = None
    for _ in range(10):
        params = {"limit": 2} | ({"cursor": cursor} if cursor else {})
        r = await client.get("/api/v1/tickets/feed", headers=auth(owner), params=params)
        assert r.status_code == 200, r.text
        body = r.json()
        seen += [item["id"] for item in body["items"]]
        cursor = body.get("next_cursor")
        if not cursor:
            break
    # All 5, newest first, none twice, none missing.
    assert seen == list(reversed(created))


async def test_malformed_cursor_is_a_bad_request(
    client: AsyncClient, make_user: MakeUser
) -> None:
    # HANDOVER §5 #13: a broken cursor is bad INPUT (400), not a missing
    # ticket (404).
    user = await make_user("requester")
    r = await client.get(
        "/api/v1/tickets/feed", headers=auth(user), params={"cursor": "not-a-cursor"}
    )
    assert r.status_code == 400, r.text


# ---- Moving a ticket to another category ---------------------------------------
async def test_category_change_moves_team_and_recomputes_sla(
    client: AsyncClient, make_user: MakeUser, categories: dict[str, Category]
) -> None:
    # Before the fix: 500 "Object of type UUID is not JSON serializable".
    owner = await make_user("requester")
    admin = await make_user("admin")
    t = await new_ticket(client, owner, categories["network"])

    r = await client.patch(
        f"/api/v1/tickets/{t['id']}",
        headers=auth(admin),
        json={"category_id": str(categories["accounts"].id)},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["team"]["slug"] == "accounts"
    # §5 #4: the deadline follows the NEW category, counted from creation.
    created = datetime.fromisoformat(body["created_at"])
    due = datetime.fromisoformat(body["sla_due_at"])
    assert due - created == timedelta(hours=categories["accounts"].sla_hours)


async def test_category_change_notifies_new_team_and_rings_both_rooms(
    client: AsyncClient,
    make_user: MakeUser,
    teams: dict[str, Team],
    categories: dict[str, Category],
) -> None:
    owner = await make_user("requester")
    admin = await make_user("admin")
    accounts_agent = await make_user("agent", team=teams["accounts"])
    t = await new_ticket(client, owner, categories["network"])

    # Listen on the same PostgreSQL channel the WebSocket hub listens on.
    # Every pg_notify the API sends lands in `rooms`.
    rooms: set[str] = set()
    url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    listener = await asyncpg.connect(url)
    await listener.add_listener(
        TICKET_CHANNEL, lambda *args: rooms.update(json.loads(args[3])["rooms"])
    )
    try:
        r = await client.patch(
            f"/api/v1/tickets/{t['id']}",
            headers=auth(admin),
            json={"category_id": str(categories["accounts"].id)},
        )
        assert r.status_code == 200, r.text
        await asyncio.sleep(0.3)  # NOTIFY arrives just after COMMIT
    finally:
        await listener.close()

    # §5 #11: the OLD team's open lists must refresh too (the ticket left).
    assert team_room(teams["network"].id) in rooms
    assert team_room(teams["accounts"].id) in rooms

    # §5 #3: the NEW team is told it has a new ticket.
    async with AsyncSessionLocal() as db:
        notified = set(
            await db.scalars(
                select(Notification.user_id).where(
                    Notification.payload["ticket_id"].astext == t["id"]
                )
            )
        )
    assert accounts_agent.id in notified
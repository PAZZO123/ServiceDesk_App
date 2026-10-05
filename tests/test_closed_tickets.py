# ============================================================
#  tests/test_closed_tickets.py - a closed ticket is final.
#  Nobody (requester, agent, admin) comments, uploads, edits a
#  comment, claims, assigns or reassigns it.
# ============================================================
from dataclasses import dataclass

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.db.session import AsyncSessionLocal
from app.models.tag import Tag
from app.models.team import Category, Team
from app.models.ticket import Comment
from app.models.user import User
from tests.conftest import MakeUser, auth
from tests.test_attachments import TINY_PNG
from tests.test_tickets import new_ticket


@dataclass
class ClosedWorld:
    requester: User
    agent: User
    admin: User
    ticket_id: str
    agent_comment_id: str


async def move(client: AsyncClient, user: User, ticket_id: str, status: str) -> None:
    r = await client.post(
        f"/api/v1/tickets/{ticket_id}/status", headers=auth(user), json={"status": status}
    )
    assert r.status_code == 200, r.text


@pytest.fixture
async def closed(
    client: AsyncClient,
    make_user: MakeUser,
    teams: dict[str, Team],
    categories: dict[str, Category],
) -> ClosedWorld:
    requester = await make_user("requester")
    agent = await make_user("agent", team=teams["network"])
    admin = await make_user("admin")
    t = await new_ticket(client, requester, categories["network"])

    # While open, the agent claims it and replies: all allowed.
    r = await client.post(f"/api/v1/tickets/{t['id']}/claim", headers=auth(agent))
    assert r.status_code == 200, r.text
    r = await client.post(
        f"/api/v1/tickets/{t['id']}/comments", headers=auth(agent), json={"body": "Fixed it."}
    )
    assert r.status_code == 201, r.text
    comment_id = r.json()["id"]

    await move(client, agent, t["id"], "resolved")
    await move(client, requester, t["id"], "closed")
    return ClosedWorld(requester, agent, admin, t["id"], comment_id)


async def comment_count(ticket_id: str) -> int:
    async with AsyncSessionLocal() as db:
        return await db.scalar(
            select(func.count(Comment.id)).where(Comment.ticket_id == ticket_id)
        ) or 0


@pytest.mark.parametrize("who", ["requester", "agent", "admin"])
async def test_nobody_comments_on_a_closed_ticket(
    client: AsyncClient, closed: ClosedWorld, who: str
) -> None:
    user = getattr(closed, who)
    r = await client.post(
        f"/api/v1/tickets/{closed.ticket_id}/comments",
        headers=auth(user),
        json={"body": "One more thing..."},
    )
    assert r.status_code == 403, r.text
    assert "closed" in r.json()["error"]["message"]


@pytest.mark.parametrize("who", ["requester", "agent"])
async def test_status_note_is_no_back_door(
    client: AsyncClient, closed: ClosedWorld, who: str
) -> None:
    # "closed -> closed" plus a note used to save the note anyway.
    before = await comment_count(closed.ticket_id)
    r = await client.post(
        f"/api/v1/tickets/{closed.ticket_id}/status",
        headers=auth(getattr(closed, who)),
        json={"status": "closed", "comment": "Sneaky reply"},
    )
    assert r.status_code == 403, r.text
    assert await comment_count(closed.ticket_id) == before


@pytest.mark.parametrize("who", ["agent", "admin"])
async def test_nobody_claims_a_closed_ticket(
    client: AsyncClient, closed: ClosedWorld, who: str
) -> None:
    r = await client.post(
        f"/api/v1/tickets/{closed.ticket_id}/claim", headers=auth(getattr(closed, who))
    )
    assert r.status_code == 403, r.text


@pytest.mark.parametrize("assignee", [None, "admin"])
async def test_admin_cannot_reassign_or_unassign_a_closed_ticket(
    client: AsyncClient, closed: ClosedWorld, assignee: str | None
) -> None:
    target = str(getattr(closed, assignee).id) if assignee else None
    r = await client.post(
        f"/api/v1/tickets/{closed.ticket_id}/assign",
        headers=auth(closed.admin),
        json={"assignee_id": target},
    )
    assert r.status_code == 403, r.text
    # The agent who did the work stays recorded as the assignee.
    r = await client.get(f"/api/v1/tickets/{closed.ticket_id}", headers=auth(closed.admin))
    assert r.json()["assignee"]["id"] == str(closed.agent.id)


async def test_no_uploads_and_no_comment_edits_when_closed(
    client: AsyncClient, closed: ClosedWorld
) -> None:
    png = {"file": ("screen.png", TINY_PNG, "image/png")}
    r = await client.post(
        f"/api/v1/tickets/{closed.ticket_id}/attachments", headers=auth(closed.requester), files=png
    )
    assert r.status_code == 403, r.text
    r = await client.post(
        f"/api/v1/comments/{closed.agent_comment_id}/attachments",
        headers=auth(closed.agent),
        files=png,
    )
    assert r.status_code == 403, r.text
    r = await client.patch(
        f"/api/v1/comments/{closed.agent_comment_id}",
        headers=auth(closed.agent),
        json={"body": "Rewriting history"},
    )
    assert r.status_code == 403, r.text


async def test_closing_with_a_note_still_works(
    client: AsyncClient,
    make_user: MakeUser,
    categories: dict[str, Category],
) -> None:
    requester = await make_user("requester")
    t = await new_ticket(client, requester, categories["network"])
    r = await client.post(
        f"/api/v1/tickets/{t['id']}/status",
        headers=auth(requester),
        json={"status": "closed", "comment": "Sorted it myself, thanks."},
    )
    assert r.status_code == 200, r.text
    assert await comment_count(t["id"]) == 1


async def test_tags_stay_editable_on_a_closed_ticket(
    client: AsyncClient, closed: ClosedWorld
) -> None:
    async with AsyncSessionLocal() as db:
        tag = Tag(name="printer-outage")
        db.add(tag)
        await db.commit()
    r = await client.put(
        f"/api/v1/tickets/{closed.ticket_id}/tags",
        headers=auth(closed.agent),
        json={"tag_ids": [str(tag.id)]},
    )
    assert r.status_code == 200, r.text

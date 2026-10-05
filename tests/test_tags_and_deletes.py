# ============================================================
#  tests/test_tags_and_deletes.py
#  (1) Staff can create tags (POST /tags) and use them at once.
#  (2) On a resolved or closed ticket only a moderator (admin) may
#      delete comments and files - not even their own author.
# ============================================================
import pytest
from httpx import AsyncClient

from app.models.team import Category, Team
from app.models.user import User
from tests.conftest import MakeUser, auth
from tests.test_attachments import TINY_PNG
from tests.test_tickets import new_ticket

# ---- (1) creating tags --------------------------------------------------


async def create_tag(client: AsyncClient, user: User, name: str, color: str | None = None):
    body = {"name": name} if color is None else {"name": name, "color": color}
    return await client.post("/api/v1/tags", headers=auth(user), json=body)


@pytest.mark.parametrize("role", ["agent", "admin"])
async def test_staff_create_a_tag_and_use_it(
    client: AsyncClient, make_user: MakeUser, categories: dict[str, Category], role: str
) -> None:
    staff = await make_user(role)
    requester = await make_user("requester", email="req@example.com")
    t = await new_ticket(client, requester, categories["network"])

    r = await create_tag(client, staff, "  Printer   Outage ", "#DC2626")
    assert r.status_code == 201, r.text
    tag = r.json()
    assert tag["name"] == "printer-outage"  # one spelling for everyone
    assert tag["color"] == "#DC2626"

    # The bug the owner saw: a tag no ticket uses yet must still be listed.
    r = await client.get("/api/v1/tags", headers=auth(staff))
    assert [x["name"] for x in r.json()] == ["printer-outage"]

    if role == "agent":
        return  # agents only see their team's tickets; admin tags below
    r = await client.put(
        f"/api/v1/tickets/{t['id']}/tags", headers=auth(staff), json={"tag_ids": [tag["id"]]}
    )
    assert r.status_code == 200, r.text
    assert [x["name"] for x in r.json()["tags"]] == ["printer-outage"]


async def test_duplicate_tag_is_409_whatever_the_case(
    client: AsyncClient, make_user: MakeUser
) -> None:
    agent = await make_user("agent")
    assert (await create_tag(client, agent, "vpn")).status_code == 201
    r = await create_tag(client, agent, "VPN")
    assert r.status_code == 409, r.text
    assert r.json()["error"]["code"] == "tag_already_exists"


async def test_requester_cannot_create_tags(client: AsyncClient, make_user: MakeUser) -> None:
    requester = await make_user("requester")
    assert (await create_tag(client, requester, "my-tag")).status_code == 403


@pytest.mark.parametrize(
    "name, color",
    [("x", None), ("no_underscores", None), ("ok-name", "red"), ("ok-name", "#12345")],
)
async def test_bad_tag_input_is_422(
    client: AsyncClient, make_user: MakeUser, name: str, color: str | None
) -> None:
    agent = await make_user("agent")
    r = await create_tag(client, agent, name, color)
    assert r.status_code == 422, r.text


# ---- (2) deleting on a finished ticket ----------------------------------


async def setup_ticket(
    client: AsyncClient,
    make_user: MakeUser,
    teams: dict[str, Team],
    categories: dict[str, Category],
) -> tuple[User, User, User, str, str, str]:
    requester = await make_user("requester")
    agent = await make_user("agent", team=teams["network"])
    admin = await make_user("admin")
    t = await new_ticket(client, requester, categories["network"])

    r = await client.post(
        f"/api/v1/tickets/{t['id']}/comments", headers=auth(agent), json={"body": "Rebooted it."}
    )
    assert r.status_code == 201, r.text
    comment_id = r.json()["id"]
    r = await client.post(
        f"/api/v1/tickets/{t['id']}/attachments",
        headers=auth(requester),
        files={"file": ("screen.png", TINY_PNG, "image/png")},
    )
    assert r.status_code == 201, r.text
    return requester, agent, admin, t["id"], comment_id, r.json()["id"]


async def finish(client: AsyncClient, agent: User, requester: User, ticket_id: str, status: str):
    r = await client.post(
        f"/api/v1/tickets/{ticket_id}/status", headers=auth(agent), json={"status": "resolved"}
    )
    assert r.status_code == 200, r.text
    if status == "closed":
        r = await client.post(
            f"/api/v1/tickets/{ticket_id}/status",
            headers=auth(requester),
            json={"status": "closed"},
        )
        assert r.status_code == 200, r.text


@pytest.mark.parametrize("status", ["resolved", "closed"])
async def test_only_admin_deletes_on_a_finished_ticket(
    client: AsyncClient,
    make_user: MakeUser,
    teams: dict[str, Team],
    categories: dict[str, Category],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    status: str,
) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path)
    requester, agent, admin, ticket_id, comment_id, file_id = await setup_ticket(
        client, make_user, teams, categories
    )
    await finish(client, agent, requester, ticket_id, status)

    # The authors themselves: refused.
    r = await client.delete(f"/api/v1/comments/{comment_id}", headers=auth(agent))
    assert r.status_code == 403, r.text
    r = await client.delete(f"/api/v1/attachments/{file_id}", headers=auth(requester))
    assert r.status_code == 403, r.text

    # The admin (content.moderate): allowed.
    r = await client.delete(f"/api/v1/comments/{comment_id}", headers=auth(admin))
    assert r.status_code == 204, r.text
    r = await client.delete(f"/api/v1/attachments/{file_id}", headers=auth(admin))
    assert r.status_code == 204, r.text


async def test_authors_still_delete_their_own_while_the_ticket_is_open(
    client: AsyncClient,
    make_user: MakeUser,
    teams: dict[str, Team],
    categories: dict[str, Category],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path)
    requester, agent, _, _, comment_id, file_id = await setup_ticket(
        client, make_user, teams, categories
    )
    r = await client.delete(f"/api/v1/comments/{comment_id}", headers=auth(agent))
    assert r.status_code == 204, r.text
    r = await client.delete(f"/api/v1/attachments/{file_id}", headers=auth(requester))
    assert r.status_code == 204, r.text

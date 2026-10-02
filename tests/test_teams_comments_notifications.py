from httpx import AsyncClient

from app.models.team import Category, Team
from app.models.user import User
from tests.conftest import MakeUser, auth


async def new_ticket(client: AsyncClient, user: User, category: Category) -> str:
    r = await client.post(
        "/api/v1/tickets",
        headers=auth(user),
        json={
            "title": "Monitor flickers",
            "description": "Every few seconds since Monday.",
            "category_id": str(category.id),
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def comment(
    client: AsyncClient, user: User, ticket_id: str, body: str, internal: bool = False
) -> str:
    r = await client.post(
        f"/api/v1/tickets/{ticket_id}/comments",
        headers=auth(user),
        json={"body": body, "is_internal": internal},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


#  Teams 
async def test_joining_a_team_is_what_makes_its_tickets_visible(
    client: AsyncClient,
    make_user: MakeUser,
    teams: dict[str, Team],
    categories: dict[str, Category],
) -> None:
    admin = await make_user("admin")
    agent = await make_user("agent")  # in NO team yet
    requester = await make_user("requester")
    ticket_id = await new_ticket(client, requester, categories["network"])
    url = f"/api/v1/tickets/{ticket_id}"

    assert (await client.get(url, headers=auth(agent))).status_code == 404

    r = await client.post(
        f"/api/v1/teams/{teams['network'].id}/members",
        headers=auth(admin),
        json={"user_id": str(agent.id)},
    )
    assert r.status_code == 201, r.text
    assert (await client.get(url, headers=auth(agent))).status_code == 200

    r = await client.delete(
        f"/api/v1/teams/{teams['network'].id}/members/{agent.id}", headers=auth(admin)
    )
    assert r.status_code == 200, r.text
    assert (await client.get(url, headers=auth(agent))).status_code == 404


async def test_team_membership_rules(
    client: AsyncClient, make_user: MakeUser, teams: dict[str, Team]
) -> None:
    admin = await make_user("admin")
    agent = await make_user("agent", team=teams["network"])
    requester = await make_user("requester")
    members_url = f"/api/v1/teams/{teams['network'].id}/members"

    # Only staff can be members.
    r = await client.post(members_url, headers=auth(admin), json={"user_id": str(requester.id)})
    assert r.status_code == 400, r.text
    # Twice -> 409.
    r = await client.post(members_url, headers=auth(admin), json={"user_id": str(agent.id)})
    assert r.status_code == 409, r.text
    # Agents may not manage teams.
    r = await client.post(members_url, headers=auth(agent), json={"user_id": str(admin.id)})
    assert r.status_code == 403, r.text
    # Promote to lead.
    r = await client.patch(
        f"{members_url}/{agent.id}", headers=auth(admin), json={"role_in_team": "lead"}
    )
    assert r.status_code == 200, r.text
    assert r.json()["role_in_team"] == "lead"


async def test_removing_a_member_reports_their_open_tickets(
    client: AsyncClient,
    make_user: MakeUser,
    teams: dict[str, Team],
    categories: dict[str, Category],
) -> None:
    admin = await make_user("admin")
    agent = await make_user("agent", team=teams["network"])
    requester = await make_user("requester")
    ticket_id = await new_ticket(client, requester, categories["network"])
    await client.post(f"/api/v1/tickets/{ticket_id}/claim", headers=auth(agent))

    r = await client.delete(
        f"/api/v1/teams/{teams['network'].id}/members/{agent.id}", headers=auth(admin)
    )
    assert r.json() == {"removed": True, "open_tickets_still_assigned": 1}


#  Comments 
async def test_only_the_author_edits_a_comment(
    client: AsyncClient,
    make_user: MakeUser,
    teams: dict[str, Team],
    categories: dict[str, Category],
) -> None:
    requester = await make_user("requester")
    agent = await make_user("agent", team=teams["network"])
    ticket_id = await new_ticket(client, requester, categories["network"])
    comment_id = await comment(client, requester, ticket_id, "It also beeps.")

    r = await client.patch(
        f"/api/v1/comments/{comment_id}", headers=auth(agent), json={"body": "Changed by agent"}
    )
    assert r.status_code == 403, r.text

    r = await client.patch(
        f"/api/v1/comments/{comment_id}", headers=auth(requester), json={"body": "It also beeps twice."}
    )
    assert r.status_code == 200, r.text
    assert r.json()["body"] == "It also beeps twice."


async def test_internal_note_is_invisible_not_forbidden(
    client: AsyncClient,
    make_user: MakeUser,
    teams: dict[str, Team],
    categories: dict[str, Category],
) -> None:
    requester = await make_user("requester")
    agent = await make_user("agent", team=teams["network"])
    ticket_id = await new_ticket(client, requester, categories["network"])
    note_id = await comment(client, agent, ticket_id, "User pressed the wrong button.", internal=True)

    # 404, not 403: a 403 would confirm that a hidden note exists.
    r = await client.patch(
        f"/api/v1/comments/{note_id}", headers=auth(requester), json={"body": "x"}
    )
    assert r.status_code == 404, r.text
    r = await client.delete(f"/api/v1/comments/{note_id}", headers=auth(requester))
    assert r.status_code == 404, r.text


async def test_delete_own_or_as_moderator(
    client: AsyncClient,
    make_user: MakeUser,
    teams: dict[str, Team],
    categories: dict[str, Category],
) -> None:
    requester = await make_user("requester")
    agent = await make_user("agent", team=teams["network"])
    admin = await make_user("admin")
    ticket_id = await new_ticket(client, requester, categories["network"])
    first = await comment(client, requester, ticket_id, "First message.")
    second = await comment(client, requester, ticket_id, "Second message.")

    # An agent works the ticket but is not a moderator.
    assert (await client.delete(f"/api/v1/comments/{first}", headers=auth(agent))).status_code == 403
    # The author may.
    assert (await client.delete(f"/api/v1/comments/{first}", headers=auth(requester))).status_code == 204
    # content.moderate (admin) may delete anyone's.
    assert (await client.delete(f"/api/v1/comments/{second}", headers=auth(admin))).status_code == 204


#  Notifications 
async def test_notifications_follow_the_comment_rules(
    client: AsyncClient,
    make_user: MakeUser,
    teams: dict[str, Team],
    categories: dict[str, Category],
) -> None:
    requester = await make_user("requester")
    agent = await make_user("agent", team=teams["network"])
    ticket_id = await new_ticket(client, requester, categories["network"])

    await comment(client, agent, ticket_id, "Secret: it is the cable.", internal=True)
    await comment(client, agent, ticket_id, "Please try another cable.")

    r = await client.get("/api/v1/notifications", headers=auth(requester))
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    # Only the PUBLIC comment reached the requester.
    assert [n["payload"]["preview"] for n in items] == ["Please try another cable."]

    r = await client.get("/api/v1/notifications/unread-count", headers=auth(requester))
    assert r.json() == {"unread": 1}


async def test_someone_elses_notification_is_not_found(
    client: AsyncClient,
    make_user: MakeUser,
    teams: dict[str, Team],
    categories: dict[str, Category],
) -> None:
    requester = await make_user("requester")
    agent = await make_user("agent", team=teams["network"])
    ticket_id = await new_ticket(client, requester, categories["network"])
    await comment(client, agent, ticket_id, "On my way.")
    notification_id = (
        await client.get("/api/v1/notifications", headers=auth(requester))
    ).json()["items"][0]["id"]

    r = await client.post(f"/api/v1/notifications/{notification_id}/read", headers=auth(agent))
    assert r.status_code == 404, r.text

    r = await client.post(f"/api/v1/notifications/{notification_id}/read", headers=auth(requester))
    assert r.status_code == 200, r.text
    assert r.json()["read_at"] is not None


async def test_read_all(
    client: AsyncClient,
    make_user: MakeUser,
    teams: dict[str, Team],
    categories: dict[str, Category],
) -> None:
    requester = await make_user("requester")
    agent = await make_user("agent", team=teams["network"])
    ticket_id = await new_ticket(client, requester, categories["network"])
    for text in ["One.", "Two.", "Three."]:
        await comment(client, agent, ticket_id, text)

    unread = (await client.get("/api/v1/notifications/unread-count", headers=auth(requester))).json()
    assert unread == {"unread": 3}
    r = await client.post("/api/v1/notifications/read-all", headers=auth(requester))
    assert r.status_code == 204, r.text
    unread = (await client.get("/api/v1/notifications/unread-count", headers=auth(requester))).json()
    assert unread == {"unread": 0}
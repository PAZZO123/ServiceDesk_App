from httpx import AsyncClient

from app.models.team import Category
from app.models.user import User
from tests.conftest import MakeUser, auth


async def new_ticket(
    client: AsyncClient, user: User, category: Category, title: str, description: str
) -> str:
    r = await client.post(
        "/api/v1/tickets",
        headers=auth(user),
        json={"title": title, "description": description, "category_id": str(category.id)},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def search(client: AsyncClient, user: User, **params: str) -> list[str]:
    r = await client.get("/api/v1/tickets", headers=auth(user), params=params)
    assert r.status_code == 200, r.text
    return [t["title"] for t in r.json()["items"]]


async def test_search_matches_word_forms(
    client: AsyncClient, make_user: MakeUser, categories: dict[str, Category]
) -> None:
    user = await make_user("requester")
    await new_ticket(client, user, categories["network"], "Printer offline", "It shows an error light.")
    await new_ticket(client, user, categories["network"], "Wi-Fi drops", "Lost connection in room 4.")

    assert await search(client, user, q="printers") == ["Printer offline"]
    assert await search(client, user, q="connecting") == ["Wi-Fi drops"]


async def test_search_syntax_phrase_or_and_exclude(
    client: AsyncClient, make_user: MakeUser, categories: dict[str, Category]
) -> None:
    user = await make_user("requester")
    await new_ticket(client, user, categories["network"], "Printer jammed", "Paper stuck in tray two.")
    await new_ticket(client, user, categories["network"], "Printer offline", "Paper is fine, no network.")

    # The same syntax people know from web search engines.
    assert await search(client, user, q='"paper stuck"') == ["Printer jammed"]
    assert await search(client, user, q="printer -network") == ["Printer jammed"]
    assert set(await search(client, user, q="jammed or offline")) == {
        "Printer jammed",
        "Printer offline",
    }


async def test_strange_input_never_breaks_the_query(
    client: AsyncClient, make_user: MakeUser
) -> None:
    user = await make_user("requester")
    for q in ["'); DROP TABLE tickets; --", "a & | ! : *", '"unclosed', "the"]:
        r = await client.get("/api/v1/tickets", headers=auth(user), params={"q": q})
        assert r.status_code == 200, (q, r.text)


async def test_search_still_respects_permissions(
    client: AsyncClient, make_user: MakeUser, categories: dict[str, Category]
) -> None:
    alice = await make_user("requester", email="alice@example.com")
    bob = await make_user("requester", email="bob@example.com")
    await new_ticket(client, alice, categories["network"], "Salary spreadsheet locked", "Cannot open it.")

    assert await search(client, alice, q="salary") == ["Salary spreadsheet locked"]
    # The search is one more WHERE condition next to the visibility ones:
    # it can narrow what you see, never widen it.
    assert await search(client, bob, q="salary") == []


async def test_relevance_puts_title_matches_first(
    client: AsyncClient, make_user: MakeUser, categories: dict[str, Category]
) -> None:
    user = await make_user("requester")
    # Created FIRST, so "newest first" would put it LAST.
    await new_ticket(client, user, categories["network"], "VPN will not connect", "Error 809 at home.")
    await new_ticket(client, user, categories["network"], "Laptop is slow", "Also the vpn drops sometimes.")

    newest_first = await search(client, user, q="vpn")
    assert newest_first == ["Laptop is slow", "VPN will not connect"]

    # Title words have weight A, description words weight B.
    best_first = await search(client, user, q="vpn", sort="relevance")
    assert best_first == ["VPN will not connect", "Laptop is slow"]


async def test_relevance_without_text_is_rejected(
    client: AsyncClient, make_user: MakeUser
) -> None:
    user = await make_user("requester")
    r = await client.get("/api/v1/tickets", headers=auth(user), params={"sort": "relevance"})
    assert r.status_code == 400, r.text


async def test_impossible_date_range_is_a_bad_request(
    client: AsyncClient, make_user: MakeUser
) -> None:
    user = await make_user("requester")
    r = await client.get(
        "/api/v1/tickets",
        headers=auth(user),
        params={"created_after": "2026-10-01T00:00:00Z", "created_before": "2026-09-01T00:00:00Z"},
    )
    assert r.status_code == 400, r.text
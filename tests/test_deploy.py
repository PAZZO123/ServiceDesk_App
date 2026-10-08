# ============================================================
#  tests/test_deploy.py - the pieces added to run on Render.
# ============================================================
import json
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core import email
from app.core.config import Settings, settings
from app.frontend import mount_frontend

SECRET = "x" * 40


# ---- config: the URL Render gives us works as it is ---------------------


@pytest.mark.parametrize(
    "given",
    ["postgres://u:p@db:5432/sd", "postgresql://u:p@db:5432/sd", "postgresql+asyncpg://u:p@db:5432/sd"],
)
def test_database_url_gets_the_asyncpg_driver(given: str) -> None:
    s = Settings(_env_file=None, DATABASE_URL=given, SECRET_KEY=SECRET)  # type: ignore[call-arg]
    assert s.DATABASE_URL == "postgresql+asyncpg://u:p@db:5432/sd"
    assert s.sync_database_url == "postgresql://u:p@db:5432/sd"  # the realtime listener


def test_only_database_url_and_secret_are_required(monkeypatch: pytest.MonkeyPatch) -> None:
    # Render has no POSTGRES_* and no TEST_DATABASE_URL.
    for name in ("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB", "TEST_DATABASE_URL"):
        monkeypatch.delenv(name, raising=False)
    Settings(_env_file=None, DATABASE_URL="postgresql://u:p@h/d", SECRET_KEY=SECRET)  # type: ignore[call-arg]


def test_links_in_emails_use_the_render_address(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://servicedesk.onrender.com")
    monkeypatch.delenv("FRONTEND_URL", raising=False)
    s = Settings(_env_file=None, DATABASE_URL="postgresql://u:p@h/d", SECRET_KEY=SECRET)  # type: ignore[call-arg]
    assert s.FRONTEND_URL == "https://servicedesk.onrender.com"
    assert s.BACKEND_URL == "https://servicedesk.onrender.com"


# ---- the React app served by FastAPI ------------------------------------


@pytest.fixture
def dist(tmp_path: Path) -> Path:
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<div id=root>APP</div>")
    (tmp_path / "assets" / "index-abc.js").write_text("console.log(1)")
    (tmp_path / "favicon.svg").write_text("<svg/>")
    (tmp_path.parent / "secret.txt").write_text("do not serve")
    return tmp_path


async def spa_client(dist: Path) -> AsyncClient:
    app = FastAPI()

    @app.get("/api/v1/ping")
    async def ping() -> dict[str, str]:
        return {"pong": "yes"}

    assert mount_frontend(app, dist)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_pages_of_the_app_get_index_html(dist: Path) -> None:
    async with await spa_client(dist) as c:
        for path in ["/", "/login", "/app/tickets/123"]:
            r = await c.get(path)
            assert r.status_code == 200, path
            assert "APP" in r.text
        assert (await c.get("/assets/index-abc.js")).text == "console.log(1)"
        assert (await c.get("/favicon.svg")).text == "<svg/>"


async def test_api_routes_win_and_unknown_api_paths_are_404(dist: Path) -> None:
    async with await spa_client(dist) as c:
        assert (await c.get("/api/v1/ping")).json() == {"pong": "yes"}
        r = await c.get("/api/v1/does-not-exist")
        assert r.status_code == 404
        assert "APP" not in r.text


async def test_no_file_outside_dist_is_served(dist: Path) -> None:
    async with await spa_client(dist) as c:
        r = await c.get("/%2e%2e/secret.txt")
        assert "do not serve" not in r.text


def test_no_build_means_no_frontend_routes(tmp_path: Path) -> None:
    app = FastAPI()
    assert mount_frontend(app, tmp_path / "missing") is False
    assert len(app.routes) == len(FastAPI().routes)  # nothing added


# ---- email through Brevo (HTTPS) -----------------------------------------


@pytest.fixture
def brevo(monkeypatch: pytest.MonkeyPatch):
    """Replace Brevo by a fake server; returns the captured requests."""
    sent: list[httpx.Request] = []
    status = {"code": 201}

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(status["code"], json={"messageId": "<1@brevo>"})

    real_client = httpx.AsyncClient

    def fake_client(*args, **kwargs):
        return real_client(*args, transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(email.httpx, "AsyncClient", fake_client)
    monkeypatch.setattr(settings, "BREVO_API_KEY", "test-key-not-real")
    monkeypatch.setattr(settings, "MAIL_FROM", "sender@example.com")
    return sent, status


async def test_reset_email_goes_through_brevo(brevo) -> None:
    sent, _ = brevo
    await email.send_password_reset_email(to="claire@example.com", full_name="Claire", token="tok123")

    assert len(sent) == 1
    request = sent[0]
    assert str(request.url) == email.BREVO_URL
    assert request.headers["api-key"] == "test-key-not-real"
    body = json.loads(request.content)
    assert body["sender"]["email"] == "sender@example.com"
    assert body["to"] == [{"email": "claire@example.com"}]
    assert "tok123" in body["htmlContent"] and "tok123" in body["textContent"]


@pytest.mark.parametrize("code, error", [(500, email.EmailServiceUnavailable), (429, email.EmailServiceUnavailable), (401, email.EmailRejected)])
async def test_brevo_errors(brevo, code: int, error: type[Exception]) -> None:
    _, status = brevo
    status["code"] = code
    with pytest.raises(error):
        await email.send_welcome_email(to="claire@example.com", full_name="Claire")


def test_only_temporary_brevo_errors_are_retried() -> None:
    from app.workers.email_tasks import RETRYABLE

    assert issubclass(email.EmailServiceUnavailable, RETRYABLE)
    assert not issubclass(email.EmailRejected, RETRYABLE)

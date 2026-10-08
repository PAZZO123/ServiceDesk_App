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


def test_shared_keyvalue_gets_our_own_database_numbers() -> None:
    # Render's connection string has no database number (shared bizpilot-redis).
    s = Settings(  # type: ignore[call-arg]
        _env_file=None, DATABASE_URL="postgresql://u:p@h/d", SECRET_KEY=SECRET,
        KEYVALUE_URL="redis://red-abc123:6379", KEYVALUE_DB_BASE=10,
    )
    assert (s.REDIS_URL, s.CELERY_BROKER_URL, s.CELERY_RESULT_BACKEND) == (
        "redis://red-abc123:6379/10",
        "redis://red-abc123:6379/11",
        "redis://red-abc123:6379/12",
    )


def test_without_keyvalue_url_the_local_urls_stay() -> None:
    # The local .env: /0, /1, /2 must not move.
    s = Settings(  # type: ignore[call-arg]
        _env_file=None, DATABASE_URL="postgresql://u:p@h/d", SECRET_KEY=SECRET,
        REDIS_URL="redis://127.0.0.1:6379/0", CELERY_BROKER_URL="redis://127.0.0.1:6379/1",
        CELERY_RESULT_BACKEND="redis://u:pw@127.0.0.1:6379/2",
    )
    assert s.REDIS_URL.endswith(":6379/0")
    assert s.CELERY_BROKER_URL.endswith(":6379/1")
    assert s.CELERY_RESULT_BACKEND == "redis://u:pw@127.0.0.1:6379/2"


def test_celery_really_uses_our_database_numbers_on_render() -> None:
    # The bug this guards against: Celery reads CELERY_BROKER_URL from the
    # environment itself. A fresh process with Render's environment must end
    # up on database 11 (queue) and 12 (results), never on BizPilot's 0.
    import os
    import subprocess
    import sys

    env = {
        k: v for k, v in os.environ.items()
        if k not in {"CELERY_BROKER_URL", "CELERY_RESULT_BACKEND", "REDIS_URL"}
    }
    env.update(KEYVALUE_URL="redis://red-abc123:6379", KEYVALUE_DB_BASE="10")
    code = (
        "from app.workers.celery_app import celery_app as c;"
        "print(c.conf.broker_url, c.conf.result_backend)"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], env=env, capture_output=True, text=True, check=True
    ).stdout.split()
    assert out == ["redis://red-abc123:6379/11", "redis://red-abc123:6379/12"]


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

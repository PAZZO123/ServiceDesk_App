"""
Throwaway end-to-end test of the auth router, without main.py.

Builds a minimal FastAPI app containing ONLY the auth router, then
drives the whole flow with the test client. This works because an
APIRouter carries no dependency on the app it is mounted into.
"""

import asyncio

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.api.v1.auth import router as auth_router
from app.core.exceptions import register_exception_handlers
from app.core.security import create_email_verification_token
from app.db.session import AsyncSessionLocal, engine  # add `engine`
from app.models.user import User

EMAIL = "testflow@example.com"
PASSWORD = "correct-horse-battery"

# ---- Build a minimal app -------------------------------------------
app = FastAPI()
register_exception_handlers(app)   # so errors use our envelope
app.include_router(auth_router, prefix="/api/v1")


async def wipe() -> None:
    """Remove the test account. Profiles and tokens cascade."""
    # ==================================================================
    #  DISCARD CONNECTIONS FROM A PREVIOUS EVENT LOOP
    # ==================================================================
    # close=False is the essential detail. A normal dispose() tries to
    # close each pooled connection GRACEFULLY, which requires the event
    # loop that created it - and that loop is already gone, so the
    # cleanup itself raises "Event loop is closed".
    #
    # close=False abandons them instead: they are dropped from the pool
    # without any network conversation. The sockets are cleaned up by
    # the operating system.
    #
    # This is SQLAlchemy's documented answer for reusing an engine
    # across processes or loops.
    await engine.dispose(close=False)

    async with AsyncSessionLocal() as db:
        await db.execute(delete(User).where(User.email == EMAIL))
        await db.commit()

    # Leave nothing for the NEXT loop. These connections belong to the
    # loop we are in right now, so a normal close works here.
    await engine.dispose()


def show(label: str, response) -> None:
    body = response.json()
    code = body.get("error", {}).get("code", "")
    print(f"  {label:34} {response.status_code}  {code}")


def main() -> None:
    asyncio.run(wipe())

    with TestClient(app) as client:
        print("\n--- REGISTRATION ---")
        r = client.post("/api/v1/auth/register", json={
            "email": EMAIL, "full_name": "Test Flow", "password": PASSWORD,
        })
        show("register", r)
        assert r.status_code == 201, r.text

        r = client.post("/api/v1/auth/register", json={
            "email": EMAIL, "full_name": "Test Flow", "password": PASSWORD,
        })
        show("register again (expect 409)", r)

        print("\n--- LOGIN BEFORE VERIFYING ---")
        r = client.post("/api/v1/auth/login",
                        data={"username": EMAIL, "password": PASSWORD})
        show("login unverified (expect 403)", r)

        print("\n--- VERIFICATION ---")
        # Generate the token directly instead of reading it from the
        # emailed link. Same function the email uses.
        token = create_email_verification_token(EMAIL)
        r = client.post("/api/v1/auth/verify-email", json={"token": token})
        show("verify-email", r)

        r = client.post("/api/v1/auth/verify-email", json={"token": token})
        show("verify again (expect 409)", r)

        r = client.post("/api/v1/auth/verify-email", json={"token": "not-a-real-token"})
        show("verify bad token (expect 401)", r)

        print("\n--- LOGIN ---")
        r = client.post("/api/v1/auth/login",
                        data={"username": EMAIL, "password": PASSWORD})
        show("login", r)
        assert r.status_code == 200, r.text
        tokens = r.json()
        access, refresh_1 = tokens["access_token"], tokens["refresh_token"]
        print(f"     expires_in = {tokens['expires_in']}s, type = {tokens['token_type']}")

        r = client.post("/api/v1/auth/login",
                        data={"username": EMAIL, "password": "wrong-password"})
        show("login wrong password (expect 401)", r)

        print("\n--- PROTECTED ENDPOINT ---")
        r = client.get("/api/v1/auth/me",
                       headers={"Authorization": f"Bearer {access}"})
        show("GET /me with token", r)
        print("     ->", r.json().get("email"), "| profile tz:",
              r.json().get("profile", {}).get("timezone"))

        r = client.get("/api/v1/auth/me")
        show("GET /me no token (expect 401)", r)

        r = client.get("/api/v1/auth/me",
                       headers={"Authorization": f"Bearer {refresh_1}"})
        show("GET /me with REFRESH token (expect 401)", r)

        print("\n--- ROTATION ---")
        r = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_1})
        show("refresh", r)
        refresh_2 = r.json()["refresh_token"]
        print("     new token differs:", refresh_2 != refresh_1)

        r = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_1})
        show("reuse OLD token (expect 401)", r)

        r = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_2})
        show("good token after reuse (expect 401)", r)

        print("\n--- PROFILE UPDATE ---")
        r = client.post("/api/v1/auth/login",
                        data={"username": EMAIL, "password": PASSWORD})
        access = r.json()["access_token"]
        auth = {"Authorization": f"Bearer {access}"}

        r = client.patch("/api/v1/auth/me/profile", headers=auth,
                         json={"timezone": "Europe/London"})
        show("patch profile", r)
        print("     ->", r.json()["profile"]["timezone"],
              "| notify_email still:", r.json()["profile"]["notify_email"])

        print("\n--- ANTI-ENUMERATION ---")
        r1 = client.post("/api/v1/auth/password-reset", json={"email": EMAIL})
        r2 = client.post("/api/v1/auth/password-reset",
                         json={"email": "nobody@nowhere.com"})
        print("  real account   :", r1.json()["message"])
        print("  unknown account:", r2.json()["message"])
        print("  identical      :", r1.json() == r2.json())

    asyncio.run(wipe())
    print("\nCleaned up.\n")


main()
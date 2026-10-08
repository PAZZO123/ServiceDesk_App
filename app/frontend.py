"""Serve the built React app (frontend/dist) from FastAPI.

On Render the API and the frontend live on ONE web service, so they share one
address: the browser's relative "/api/v1" calls, the WebSocket and the SSE
stream all work with no CORS and no proxy. In development Vite serves the
frontend instead and this is not used (there is no dist folder, or uvicorn
is opened on its own port).
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

# Paths the React app must never answer: a typo in an API URL should be a
# JSON 404, not the HTML of the app with status 200.
BACKEND_PREFIXES = ("api/", "health")


def mount_frontend(app: FastAPI, dist: Path) -> bool:
    """Add the frontend routes. Call it LAST: the catch-all must come after
    every API route. Returns False (and adds nothing) without a build."""
    dist = dist.resolve()
    index = dist / "index.html"
    if not index.is_file():
        return False

    # Hashed file names (index-Ch12S_Pi.js): a new build gets new names, so
    # browsers may cache these forever.
    if (dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str) -> FileResponse:
        if path.startswith(BACKEND_PREFIXES):
            raise StarletteHTTPException(status_code=404)
        # A real file at the top of dist (favicon.svg, icons.svg)...
        candidate = (dist / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(dist):
            return FileResponse(candidate)
        # ...otherwise a page of the app (/app/tickets/123): React Router
        # reads the URL. no-cache, so a new deploy is picked up at once.
        return FileResponse(index, headers={"Cache-Control": "no-cache"})

    return True

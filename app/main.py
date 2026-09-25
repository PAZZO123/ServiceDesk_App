
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import RedirectResponse

from app.api.v1.attachments import router as attachment_router
from app.api.v1.auth import router as auth_router
from app.api.v1.catalog import router as catalog_router
from app.api.v1.comments import router as comments_router
from app.api.v1.export import router as export_router
from app.api.v1.teams import router as teams_router
from app.api.v1.ticket import router as tickets_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.db.session import check_database_connection, engine

logging.basicConfig(
    level=logging.INFO if settings.DEBUG else logging.WARNING,
    format="%(asctime)s %(levelname)-8s %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

#  LIFESPAN

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Starting %s (%s)", settings.PROJECT_NAME, settings.ENVIRONMENT)

    if await check_database_connection():
        logger.info("Database connection OK")
    else:
        logger.error("DATABASE UNREACHABLE - check that docker compose is up")

    if not settings.is_production:
        logger.info("Docs: %s/docs", settings.BACKEND_URL)

    yield 
    logger.info("Shutting down - closing database connections")
    await engine.dispose()

#  THE APPLICATION

OPENAPI_TAGS = [
    {
        "name": "Authentication",
        "description": (
            "Registration, email verification, sign-in, and password "
            "management. Refresh tokens are single-use: presenting one "
            "twice revokes the entire session."
        ),
    },
    {
        "name": "System",
        "description": "Liveness and readiness probes.",
    },
]

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.2.0",
    description=(
        "Internal IT support ticket platform.\n\n"
        "**Getting started:** register, verify your email, then press "
        "**Authorize** above and sign in with your email and password."
    ),
    openapi_tags=OPENAPI_TAGS,

    lifespan=lifespan,

    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
    openapi_url=None if settings.is_production else "/openapi.json",
)
register_exception_handlers(app)


#  MIDDLEWARE
app.add_middleware(
    GZipMiddleware,
    minimum_size=1000,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

#  SYSTEM ENDPOINTS
@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")


@app.get("/health", tags=["System"], summary="Liveness probe")
async def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.ENVIRONMENT}

@app.get("/health/ready", tags=["System"], summary="Readiness probe")
async def readiness(response: Response) -> dict[str, object]:
    db_ok = await check_database_connection()
    if not db_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ready" if db_ok else "not_ready",
        "checks": {"database": "ok" if db_ok else "unreachable"},
    }
 
#  ROUTERS
app.include_router(auth_router, prefix=settings.API_V1_PREFIX)
app.include_router(tickets_router, prefix=settings.API_V1_PREFIX)
app.include_router(catalog_router,prefix=settings.API_V1_PREFIX )
app.include_router(comments_router, prefix=settings.API_V1_PREFIX)
app.include_router(teams_router, prefix=settings.API_V1_PREFIX)
app.include_router(attachment_router, prefix=settings.API_V1_PREFIX)
app.include_router(export_router, prefix=settings.API_V1_PREFIX)
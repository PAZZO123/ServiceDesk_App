import os
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit, urlunsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = False
    PROJECT_NAME: str = "ServiceDesk"
    API_V1_PREFIX: str = "/api/v1"

    # Security
    SECRET_KEY: str = Field(min_length=32)
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    EMAIL_TOKEN_EXPIRE_HOURS: int = 24
    RESET_TOKEN_EXPIRE_MINUTES: int = 30

    # Database
    # POSTGRES_* feed docker-compose only, TEST_DATABASE_URL only pytest:
    # a hosted server (Render) has neither, so they are optional here.
    POSTGRES_USER: str = ""
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = ""
    DATABASE_URL: str
    TEST_DATABASE_URL: str = ""
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800
    DB_ECHO: bool = False

    # Redis. 127.0.0.1, not localhost: docker-compose publishes on IPv4 only,
    # and on Windows "localhost" tries IPv6 first -> 0.5 s connect timeout.
    REDIS_URL: str = "redis://127.0.0.1:6379/0"
    CELERY_BROKER_URL: str = "redis://127.0.0.1:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://127.0.0.1:6379/2"
    # Render: ONE server URL, no database number. The three URLs above are
    # built from it: cache = base, Celery queue = base + 1, results = base + 2.
    # ServiceDesk shares another app's Key Value there; its own numbers
    # (10, 11, 12) keep the two apps' keys apart.
    # Why not set CELERY_BROKER_URL on Render directly: Celery reads that
    # environment variable ITSELF and it beats the URL we pass in, so the
    # database number added here would be ignored (it would use database 0).
    KEYVALUE_URL: str = ""
    KEYVALUE_DB_BASE: int = Field(default=10, ge=0, le=13)

    # Email
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    MAIL_FROM: str = "noreply@servicedesk.local"
    MAIL_FROM_NAME: str = "ServiceDesk"
    SMTP_STARTTLS: bool = True
    # Set = send through Brevo's HTTPS API instead of SMTP. Needed on Render's
    # free plan, which blocks outgoing SMTP ports (25, 465, 587). MAIL_FROM
    # must then be a sender verified in Brevo.
    BREVO_API_KEY: str = ""

    # Uploads
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    MAX_UPLOAD_MB: int = 10
    # URLs. On Render both default to RENDER_EXTERNAL_URL, which Render sets
    # to the service's public https address: the frontend is served by this
    # same app there, so the links in emails point at the right place.
    FRONTEND_URL: str = Field(
        default_factory=lambda: os.environ.get("RENDER_EXTERNAL_URL", "http://localhost:5173")
    )
    BACKEND_URL: str = Field(
        default_factory=lambda: os.environ.get("RENDER_EXTERNAL_URL", "http://localhost:8000")
    )
    # The built React app (npm run build). Served by FastAPI when it exists.
    FRONTEND_DIST: Path = BASE_DIR / "frontend" / "dist"

    # Hosts hand out "postgres://..." or "postgresql://..." URLs; SQLAlchemy
    # async needs "postgresql+asyncpg://...". Fixing it here means the same
    # URL Render gives us works without editing it by hand.
    @field_validator("DATABASE_URL")
    @classmethod
    def use_asyncpg_driver(cls, v: str) -> str:
        for prefix in ("postgres://", "postgresql://"):
            if v.startswith(prefix):
                return "postgresql+asyncpg://" + v[len(prefix):]
        return v

    @model_validator(mode="after")
    def build_redis_urls_from_keyvalue_url(self) -> "Settings":
        if not self.KEYVALUE_URL:
            return self  # local .env: REDIS_URL /0, broker /1, backend /2 as written

        def with_db(offset: int) -> str:
            parsed = urlsplit(self.KEYVALUE_URL)
            return urlunsplit(parsed._replace(path=f"/{self.KEYVALUE_DB_BASE + offset}"))

        self.REDIS_URL = with_db(0)
        self.CELERY_BROKER_URL = with_db(1)
        self.CELERY_RESULT_BACKEND = with_db(2)
        return self

    # validator run when settings are loaded
    @field_validator("SECRET_KEY")
    @classmethod
    def secret_key_must_not_be_placeholder(cls, v: str) -> str:
        if "REPLACE_ME" in v or "change-me" in v.lower():
            raise ValueError(
                "SECRET_KEY is still the placeholder value. Generate a real "
                'one with: python -c "import secrets; '
                'print(secrets.token_urlsafe(48))"'
            )
        return v

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_MB * 1024 * 1024

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def sync_database_url(self) -> str:
        return self.DATABASE_URL.replace("+asyncpg", "")

    @property
    def cors_origins(self) -> list[str]:
        if self.is_production:
            return [self.FRONTEND_URL]
        return [
            self.FRONTEND_URL,
            "http://localhost:5173",
            "http://localhost:3000",
            "http://127.0.0.1:5173",
        ]


# the singleton accossor
@lru_cache
def get_settings() -> Settings:
    return Settings() #type:ignore[call-arg]


settings = get_settings() 

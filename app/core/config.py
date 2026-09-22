from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR=Path(__file__).resolve().parents[2]

class Settings(BaseSettings):
    model_config=SettingsConfigDict(
        env_file=BASE_DIR/".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
        
    )
    
    #Application
    ENVIRONMENT:Literal["development", "staging", "production"]="development"
    DEBUG:bool=False
    PROJECT_NAME:str="ServiceDesk"
    API_V1_PREFIX:str="/api/v1"
    
    #Security
    SECRET_KEY:str=Field(min_length=32)
    JWT_ALGORITHM:str="HS256"
    ACCES_TOKEN_EXPIRE_MINUTES:int=15
    REFRESH_TOKEN_EXPIRE_DAYS:int=7
    EMAIL_TOKEN_EXPIRE_HOURS: int = 24
    RESET_TOKEN_EXPIRE_MINUTES: int = 30
    
    #Database
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    DATABASE_URL: str
    TEST_DATABASE_URL: str
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800  
    DB_ECHO: bool = False
    
    #Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    
    #Email
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    MAIL_FROM: str = "noreply@servicedesk.local"
    MAIL_FROM_NAME: str = "ServiceDesk"
    SMTP_STARTTLS: bool = True
    
    #Uploads
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    MAX_UPLOAD_MB: int = 10
    #URLs
    FRONTEND_URL: str = "http://localhost:5173"
    BACKEND_URL: str = "http://localhost:8000"
    
    #validator run when settings are loaded
    @field_validator("SECRET_KEY")
    @classmethod
    def secret_key_must_not_be_placeholder(cls,v:str)->str:
        if "REPLACE_ME" in v or "change-me" in v.lower():
            raise ValueError(
                "SECRET_KEY is still the placeholder value. Generate a real "
                "one with: python -c \"import secrets; "
                "print(secrets.token_urlsafe(48))\""
            )
        return v
    
    @property
    def max_upload_bytes(self)->int:
        return self.MAX_UPLOAD_MB*1024*1024
    @property
    def is_production(self)->bool:
        return self.ENVIRONMENT == "production"
    @property
    def sync_database_url(self) ->str:
        return self.DATABASE_URL.replace("+asyncpg", "")
    
    @property
    def cors_origins(self)->list[str]:
        if self.is_production:
            return [self.FRONTEND_URL]
        return[
            self.FRONTEND_URL,
            "http://localhost:5173",
            "http://localhost:3000",
            "http://127.0.0.1:5173"
        ]
        
#the singleton accossor
@lru_cache
def get_settings()->Settings:
    return Settings()
settings=get_settings()
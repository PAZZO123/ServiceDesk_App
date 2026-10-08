import asyncio

import aiosmtplib
import httpx

from app.core import email
from app.workers.celery_app import celery_app

# Network trouble or a busy provider: try again. EmailRejected (bad API key,
# unverified sender) is NOT here - five retries would fail five times.
RETRYABLE = (
    aiosmtplib.SMTPException,
    OSError,
    httpx.TransportError,
    email.EmailServiceUnavailable,
)


RETRY_OPTIONS = {
    "autoretry_for": RETRYABLE,  
    "retry_backoff": True,       
    "retry_backoff_max": 600,   
    # jitter = random part of the wait. If Gmail was down for 100 emails,
    "retry_jitter": True,
    "max_retries": 5,         
}

@celery_app.task(name="email.send_verification", **RETRY_OPTIONS)
def send_verification_email(to: str, full_name: str, token: str) -> None:
    asyncio.run(email.send_verification_email(to=to, full_name=full_name, token=token))


@celery_app.task(name="email.send_welcome", **RETRY_OPTIONS)
def send_welcome_email(to: str, full_name: str) -> None:
    asyncio.run(email.send_welcome_email(to=to, full_name=full_name))


@celery_app.task(name="email.send_password_reset", **RETRY_OPTIONS)
def send_password_reset_email(to: str, full_name: str, token: str) -> None:
    asyncio.run(
        email.send_password_reset_email(to=to, full_name=full_name, token=token)
    )
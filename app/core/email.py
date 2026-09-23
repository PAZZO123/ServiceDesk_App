import logging
from email.message import EmailMessage
from pathlib import Path
from typing import Any

import aiosmtplib
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.config import settings

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates" / "email"

# Jinja2
_env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=select_autoescape(["html", "xml"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def render(template_name: str, **context: Any) -> str:
    return _env.get_template(template_name).render(**context)


# Sending
async def send_email(
    *,
    to: str,
    subject: str,
    html_body: str,
    text_body: str,
) -> None:
    if not settings.SMTP_USER and not settings.is_production:
        logger.warning("SMTP not configured - printing email instead of sending")
        print("\n" + "=" * 70)
        print(f"  TO      : {to}")
        print(f"  SUBJECT : {subject}")
        print("-" * 70)
        print(text_body)
        print("=" * 70 + "\n")
        return

    message = EmailMessage()
    message["From"] = f"{settings.MAIL_FROM_NAME} <{settings.MAIL_FROM}>"
    message["To"] = to
    message["Subject"] = subject
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")

    try:
        await aiosmtplib.send(
            message,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            start_tls=settings.SMTP_STARTTLS,
        )
        logger.info("email_sent to=%s subject=%s", to, subject)
    except Exception:
        logger.exception("email_failed to=%s subject=%s", to, subject)


# The Three Messages
async def send_verification_email(*, to: str, full_name: str, token: str) -> None:
    link = f"{settings.FRONTEND_URL}/verify-email?token={token}"
    context = {
        "full_name": full_name,
        "link": link,
        "expire_hours": settings.EMAIL_TOKEN_EXPIRE_HOURS,
        "app_name": settings.PROJECT_NAME,
    }
    await send_email(
        to=to,
        subject=f"Verify your {settings.PROJECT_NAME} account",
        html_body=render("verify_email.html", **context),
        text_body=(
            f"Hello {full_name},\n\n"
            f"Confirm your email address to activate your "
            f"{settings.PROJECT_NAME} account:\n\n{link}\n\n"
            f"This link expires in {settings.EMAIL_TOKEN_EXPIRE_HOURS} hours.\n\n"
            "If you did not create this account, you can ignore this email."
        ),
    )


async def send_welcome_email(*, to: str, full_name: str) -> None:
    context = {
        "full_name": full_name,
        "link": f"{settings.FRONTEND_URL}/login",
        "app_name": settings.PROJECT_NAME,
    }
    await send_email(
        to=to,
        subject=f"Welcome to {settings.PROJECT_NAME}",
        html_body=render("welcome.html", **context),
        text_body=(
            f"Hello {full_name},\n\n"
            f"Your {settings.PROJECT_NAME} account is now active.\n\n"
            f"Sign in here: {settings.FRONTEND_URL}/login\n\n"
            "You can raise a support ticket any time, attach screenshots, "
            "and follow progress as our team works on it."
        ),
    )


async def send_password_reset_email(*, to: str, full_name: str, token: str) -> None:
    link = f"{settings.FRONTEND_URL}/reset-password?token={token}"
    context = {
        "full_name": full_name,
        "link": link,
        "expire_minutes": settings.RESET_TOKEN_EXPIRE_MINUTES,
        "app_name": settings.PROJECT_NAME,
    }
    await send_email(
        to=to,
        subject=f"Reset your {settings.PROJECT_NAME} password",
        html_body=render("password_reset.html", **context),
        text_body=(
            f"Hello {full_name},\n\n"
            f"Use this link to choose a new password:\n\n{link}\n\n"
            f"It expires in {settings.RESET_TOKEN_EXPIRE_MINUTES} minutes.\n\n"
            "If you did not request this, ignore this email - your "
            "password has not changed."
        ),
    )

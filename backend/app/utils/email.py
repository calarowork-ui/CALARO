import logging
from typing import Optional
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from pydantic import EmailStr

from ..core.config import settings

logger = logging.getLogger(__name__)

# Validate that configuring email won't crash the server if env vars are missing
if settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD:
    conf = ConnectionConfig(
        MAIL_USERNAME=settings.SMTP_USER,
        MAIL_PASSWORD=settings.SMTP_PASSWORD,
        MAIL_FROM=settings.EMAILS_FROM_EMAIL or settings.SMTP_USER,
        MAIL_PORT=settings.SMTP_PORT or 587,
        MAIL_SERVER=settings.SMTP_HOST,
        MAIL_FROM_NAME=settings.EMAILS_FROM_NAME or "Calaro Security",
        MAIL_STARTTLS=settings.SMTP_TLS,
        MAIL_SSL_TLS=False,
        USE_CREDENTIALS=True,
        VALIDATE_CERTS=True
    )
    fm = FastMail(conf)
else:
    logger.warning("SMTP configuration is missing. MOCK email will be used.")
    fm = None

async def send_email(email_to: str, subject: str, html_content: str):
    if not fm:
        logger.info(f"\n{'='*50}\n[MOCK EMAIL to {email_to}]\nSubject: {subject}\n{html_content}\n{'='*50}\n")
        return
        
    message = MessageSchema(
        subject=subject,
        recipients=[email_to],
        body=html_content,
        subtype=MessageType.html
    )

    try:
        await fm.send_message(message)
        logger.info(f"Email sent successfully to {email_to}")
    except Exception as e:
        logger.exception(f"Failed to send email to {email_to}: {e}")

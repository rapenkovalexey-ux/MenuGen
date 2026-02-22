import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from config import SUPPORT_EMAIL

logger = logging.getLogger(__name__)

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.mail.ru")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")


async def send_support_email(
    user_id: int,
    username: str,
    subject: str,
    message: str
):
    """Send support request to admin email"""
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[МенюПро Поддержка] {subject}"
        msg["From"] = SMTP_USER
        msg["To"] = SUPPORT_EMAIL

        body = f"""
Новое обращение в поддержку:

От: @{username} (ID: {user_id})
Тема: {subject}

Сообщение:
{message}

---
Бот: МенюПро
        """
        msg.attach(MIMEText(body, "plain", "utf-8"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            if SMTP_USER and SMTP_PASSWORD:
                server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, SUPPORT_EMAIL, msg.as_string())

        logger.info(f"Support email sent from user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False

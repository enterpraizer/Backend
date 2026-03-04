import smtplib
from email.message import EmailMessage

from celery import shared_task

from src.settings import settings


@shared_task
def send_confirmation_email(to_email: str, token: str) -> None:
    confirmation_url = f"{settings.frontend_url}/auth/register_confirm?token={token}"

    text = f"""Спасибо за регистрацию!
Для подтверждения регистрации перейдите по ссылке: {confirmation_url}
"""

    message = EmailMessage()
    message.set_content(text)
    message["From"] = settings.email.username
    message["To"] = to_email
    message["Subject"] = "Подтверждение регистрации"

    with smtplib.SMTP(host=settings.email.host, port=settings.email.port) as smtp:
        smtp.starttls()
        smtp.login(
            user=settings.email.username,
            password=settings.email.password.get_secret_value(),
        )
        smtp.send_message(msg=message)

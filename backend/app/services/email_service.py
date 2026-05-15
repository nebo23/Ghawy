import os
import smtplib
from email.message import EmailMessage
from pathlib import Path
from dotenv import load_dotenv


ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=ENV_PATH)


def send_verification_email(to_email: str, code: str) -> None:
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_from = os.getenv("SMTP_FROM_EMAIL", smtp_user or "no-reply@example.com")

    if not smtp_host or not smtp_user or not smtp_password:
        raise RuntimeError("SMTP settings are missing. Set SMTP_HOST, SMTP_USER, SMTP_PASSWORD in .env")

    message = EmailMessage()
    message["Subject"] = "Your verification code"
    message["From"] = smtp_from
    message["To"] = to_email
    message.set_content(
        f"Your verification code is: {code}\n\n"
        "This code expires in 15 minutes.\n"
        "If you did not request this, ignore this email."
    )

    with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(message)

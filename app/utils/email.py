import os
import smtplib
from email.mime.text import MIMEText
from flask import current_app

def send_email(to: str, subject: str, body: str) -> bool:
    host = current_app.config.get('SMTP_HOST')
    username = current_app.config.get('SMTP_USERNAME')
    password = current_app.config.get('SMTP_PASSWORD')
    port = int(current_app.config.get('SMTP_PORT') or 587)
    sender = current_app.config.get('SMTP_SENDER')

    if not host or not username or not password or not to:
        return False

    msg = MIMEText(body, 'plain', 'utf-8')
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = to

    try:
        with smtplib.SMTP(host, port) as server:
            server.starttls()
            server.login(username, password)
            server.send_message(msg)
        return True
    except Exception:
        return False


def send_sms(phone, message):
    # Integrate with Twilio or Africa's Talking
    # Example placeholder
    print(f"Sending SMS to {phone}: {message}")
    return True

def send_web_push(user_id, title, message):
    # Integrate with web push service (e.g., OneSignal, Firebase)
    print(f"Web push to user {user_id}: {title} - {message}")
    return True
def send_email_html(to: str, subject: str, html: str) -> bool:
    host = current_app.config.get('SMTP_HOST')
    username = current_app.config.get('SMTP_USERNAME')
    password = current_app.config.get('SMTP_PASSWORD')
    port = int(current_app.config.get('SMTP_PORT') or 587)
    sender = current_app.config.get('SMTP_SENDER')

    if not host or not username or not password or not to:
        return False

    msg = MIMEText(html, 'html', 'utf-8')
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = to

    try:
        with smtplib.SMTP(host, port) as server:
            server.starttls()
            server.login(username, password)
            server.send_message(msg)
        return True
    except Exception:
        return False

import smtplib
from email.mime.text import MIMEText
from flask import current_app
import re
from typing import Optional

_EMAIL_REGEX = re.compile(r"[^@]+@[^@]+\.[^@]+")

def _is_valid_email(email: Optional[str]) -> bool:
    if not email or not isinstance(email, str):
        return False
    return bool(_EMAIL_REGEX.match(email))

def _send_email_html_sync(to: str, subject: str, html: str) -> bool:
    """
    Sends an HTML email synchronously using SMTP settings configured in Flask current_app.

    Parameters:
        to (str): Recipient email address.
        subject (str): Subject of the email.
        html (str): HTML content of the email body.

    Returns:
        bool: True if email sent successfully, False otherwise.
    """
    host = current_app.config.get('SMTP_HOST')
    username = current_app.config.get('SMTP_USERNAME')
    password = current_app.config.get('SMTP_PASSWORD')
    port = int(current_app.config.get('SMTP_PORT') or 587)
    sender = current_app.config.get('SMTP_SENDER')

    if not all([host, username, password, to, sender]):
        return False

    if not (_is_valid_email(to) and _is_valid_email(sender)):
        return False

    msg = MIMEText(html, 'html', 'utf-8')
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = to

    try:
        if port == 465:
            # SMTP over SSL
            with smtplib.SMTP_SSL(host, port, timeout=10) as server:
                server.login(username, password)
                server.send_message(msg)
        else:
            # SMTP with STARTTLS
            with smtplib.SMTP(host, port, timeout=10) as server:
                server.ehlo()
                if server.has_extn('STARTTLS'):
                    server.starttls()
                    server.ehlo()
                server.login(username, password)
                server.send_message(msg)
        return True
    except Exception:
        # Silently fail as per user request
        return False


def send_email_html(to: str, subject: str, html: str) -> bool:
    """
    Public function to send an HTML email using SMTP configured in Flask current_app.
    This wraps the internal synchronous email sending function.

    Parameters:
        to (str): Recipient email address.
        subject (str): Email subject.
        html (str): HTML content of the email body.

    Returns:
        bool: True if email sent successfully, False otherwise.
    """
    return _send_email_html_sync(to, subject, html)


def send_email(to: str, subject: str, body: str) -> bool:
    """
    Public helper that accepts a plain-text message body and sends as HTML via
    the SMTP configuration. This function preserves the original code's
    `send_email` expected by numerous blueprints.

    Parameters:
        to (str): recipient email address
        subject (str): email subject
        body (str): plain text body

    Returns:
        bool: True if email send was successful, False otherwise
    """
    if not body:
        return False
    # Convert newlines in plain text to basic <br/> for HTML rendering
    escaped = body.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    html = "<html><body>" + escaped.replace("\n", "<br/>") + "</body></html>"
    return _send_email_html_sync(to, subject, html)

"""
EmailNotifier
-------------
Fires emails in a background thread so a slow/failed send never blocks
or breaks the request that triggered it. Failures are logged, never raised
back to the caller.

Delivery methods (chosen automatically, in this order):
  1. Mailjet HTTPS API -- used when MAILJET_API_KEY and MAILJET_SECRET_KEY are set.
  2. Brevo HTTPS API   -- used when BREVO_API_KEY is set.
  3. SMTP (Gmail etc.) -- fallback for local development.

The HTTPS options work on Render's free tier, where outbound SMTP ports
(25, 465, 587) are blocked.
"""

import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from threading import Thread

import requests

logger = logging.getLogger("email_notifier")

MAILJET_API_URL = "https://api.mailjet.com/v3.1/send"
BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


class EmailNotifier:
    def __init__(self):
        # SMTP settings (local fallback)
        self.host = os.getenv("SMTP_HOST")
        self.port = int(os.getenv("SMTP_PORT", 587))
        self.username = os.getenv("SMTP_USERNAME")
        self.password = os.getenv("SMTP_PASSWORD")
        self.from_name = os.getenv("SMTP_FROM_NAME", "Finance Tracker")

        # Mailjet API settings
        self.mailjet_api_key = os.getenv("MAILJET_API_KEY")
        self.mailjet_secret_key = os.getenv("MAILJET_SECRET_KEY")
        self.mailjet_sender = os.getenv("MAILJET_SENDER_EMAIL") or self.username

        # Brevo API settings
        self.brevo_api_key = os.getenv("BREVO_API_KEY")
        self.brevo_sender = os.getenv("BREVO_SENDER_EMAIL") or self.username

    def notify_async(self, subject, body, to):
        if not to:
            return
        Thread(target=self._send_safely, args=(subject, body, to), daemon=True).start()

    def _send_safely(self, subject, body, to):
        try:
            self._send(subject, body, to)
            print(f"[EMAIL SENT] to={to} subject={subject!r}")
        except Exception as exc:
            print(f"[EMAIL FAILED] to={to} subject={subject!r} error={exc}")
            logger.error("Email send failed to %s: %s", to, exc)

    def _send(self, subject, body, to):
        if self.mailjet_api_key and self.mailjet_secret_key:
            self._send_via_mailjet(subject, body, to)
        elif self.brevo_api_key:
            self._send_via_brevo(subject, body, to)
        else:
            self._send_via_smtp(subject, body, to)

    # ------------------------------------------------------------------
    # Mailjet HTTPS API
    # ------------------------------------------------------------------
    def _send_via_mailjet(self, subject, body, to):
        if not self.mailjet_sender:
            print(f"[EMAIL SKIPPED] MAILJET_SENDER_EMAIL not set -- to={to} subject={subject!r}")
            logger.warning("MAILJET_SENDER_EMAIL not set -- skipping email to %s", to)
            return

        response = requests.post(
            MAILJET_API_URL,
            auth=(self.mailjet_api_key, self.mailjet_secret_key),
            json={
                "Messages": [
                    {
                        "From": {"Email": self.mailjet_sender, "Name": self.from_name},
                        "To": [{"Email": to}],
                        "Subject": subject,
                        "TextPart": body,
                    }
                ]
            },
            timeout=10,
        )
        if not response.ok:
            raise RuntimeError(f"Mailjet API {response.status_code}: {response.text}")

    # ------------------------------------------------------------------
    # Brevo HTTPS API
    # ------------------------------------------------------------------
    def _send_via_brevo(self, subject, body, to):
        if not self.brevo_sender:
            print(f"[EMAIL SKIPPED] BREVO_SENDER_EMAIL not set -- to={to} subject={subject!r}")
            logger.warning("BREVO_SENDER_EMAIL not set -- skipping email to %s", to)
            return

        response = requests.post(
            BREVO_API_URL,
            headers={
                "api-key": self.brevo_api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json={
                "sender": {"name": self.from_name, "email": self.brevo_sender},
                "to": [{"email": to}],
                "subject": subject,
                "textContent": body,
            },
            timeout=10,
        )
        if not response.ok:
            raise RuntimeError(f"Brevo API {response.status_code}: {response.text}")

    # ------------------------------------------------------------------
    # SMTP (local development fallback)
    # ------------------------------------------------------------------
    def _send_via_smtp(self, subject, body, to):
        if not all([self.host, self.username, self.password]):
            print(f"[EMAIL SKIPPED] SMTP not configured -- to={to} subject={subject!r}")
            logger.warning("SMTP not configured -- skipping email to %s: %s", to, subject)
            return

        msg = MIMEMultipart()
        msg["From"] = f"{self.from_name} <{self.username}>"
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(self.host, self.port, timeout=15) as server:
            server.starttls()
            server.login(self.username, self.password)
            server.sendmail(self.username, to, msg.as_string())
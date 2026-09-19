"""
EmailNotifier
-------------
Fires emails in a background thread so a slow/failed SMTP call never blocks
or breaks the request that triggered it. Failures are logged, never raised
back to the caller.
"""

import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from threading import Thread

logger = logging.getLogger("email_notifier")


class EmailNotifier:
    def __init__(self):
        self.host = os.getenv("SMTP_HOST")
        self.port = int(os.getenv("SMTP_PORT", 587))
        self.username = os.getenv("SMTP_USERNAME")
        self.password = os.getenv("SMTP_PASSWORD")
        self.from_name = os.getenv("SMTP_FROM_NAME", "Finance Tracker")

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
        if not all([self.host, self.username, self.password]):
            print(f"[EMAIL SKIPPED] SMTP not configured -- to={to} subject={subject!r}")
            logger.warning("SMTP not configured -- skipping email to %s: %s", to, subject)
            return

        msg = MIMEMultipart()
        msg["From"] = f"{self.from_name} <{self.username}>"
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(self.host, self.port) as server:
            server.starttls()
            server.login(self.username, self.password)
            server.sendmail(self.username, to, msg.as_string())

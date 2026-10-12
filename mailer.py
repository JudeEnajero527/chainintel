"""Outgoing email (digest, alerts, password reset, verification). Gmail SMTP by default."""
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, make_msgid

import config

log = logging.getLogger("chainintel.mail")

SMTP_HOST = config.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(config.get("SMTP_PORT", "587"))


def sender() -> str:
    return config.get("CHAININTEL_EMAIL")


def is_configured() -> bool:
    return bool(config.get("CHAININTEL_EMAIL") and config.get("CHAININTEL_APP_PASS"))


def app_url() -> str:
    return config.get("CHAININTEL_URL", "http://localhost:8501").rstrip("/")


def build(to: str, subject: str, text: str, html: str | None = None, headers: dict | None = None) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = formataddr(("ChainIntel", sender()))
    msg["To"] = to
    msg["Message-ID"] = make_msgid(domain="chainintel.local")
    for k, v in (headers or {}).items():
        msg[k] = v
    msg.attach(MIMEText(text, "plain", "utf-8"))
    if html:
        msg.attach(MIMEText(html, "html", "utf-8"))
    return msg


class Mailer:
    """Reuses one SMTP connection for a batch:  with Mailer() as m: m.send(msg)"""

    def __enter__(self):
        if not is_configured():
            raise RuntimeError("Email isn't configured: set CHAININTEL_EMAIL and CHAININTEL_APP_PASS in .env")
        self.server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30)
        self.server.starttls()
        self.server.login(sender(), config.get("CHAININTEL_APP_PASS"))
        return self

    def send(self, msg: MIMEMultipart):
        self.server.sendmail(sender(), [msg["To"]], msg.as_string())

    def __exit__(self, *exc):
        try:
            self.server.quit()
        except smtplib.SMTPException:
            pass


def send(to: str, subject: str, text: str, html: str | None = None) -> tuple[bool, str]:
    """One-off email. Returns (ok, error message)."""
    if not is_configured():
        return False, "Email isn't configured on this server."
    try:
        with Mailer() as m:
            m.send(build(to, subject, text, html))
        return True, ""
    except (smtplib.SMTPException, OSError) as e:
        log.warning("Email to %s failed: %s", to, e)
        return False, str(e)

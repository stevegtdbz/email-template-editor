"""
Email sending backend.

Supports:
  - SMTP (all platforms)  — smtplib, no extra dependencies
  - Outlook COM (Windows) — requires pywin32; detected at runtime
"""
from __future__ import annotations

import json
import smtplib
import sys
from dataclasses import asdict, dataclass, field
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

_CONFIG_PATH = Path.home() / ".config" / "email-templates-tool" / "smtp.json"
_PREFS_PATH  = Path.home() / ".config" / "email-templates-tool" / "prefs.json"


def load_last_to() -> str:
    if not _PREFS_PATH.exists():
        return ""
    try:
        return json.loads(_PREFS_PATH.read_text(encoding="utf-8")).get("last_to", "")
    except Exception:
        return ""


def save_last_to(to: str) -> None:
    _PREFS_PATH.parent.mkdir(parents=True, exist_ok=True)
    prefs: dict = {}
    if _PREFS_PATH.exists():
        try:
            prefs = json.loads(_PREFS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    prefs["last_to"] = to
    _PREFS_PATH.write_text(json.dumps(prefs, indent=2), encoding="utf-8")


# ── Config ─────────────────────────────────────────────────────────────────────

@dataclass
class SmtpConfig:
    host:      str  = ""
    port:      int  = 587
    username:  str  = ""
    password:  str  = ""
    from_name: str  = ""
    use_tls:   bool = True

    # ── persistence ───────────────────────────────────────────────────────────

    def save(self) -> None:
        _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        _CONFIG_PATH.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    @classmethod
    def load(cls) -> SmtpConfig:
        if _CONFIG_PATH.exists():
            try:
                data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
                return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
            except Exception:
                pass
        return cls()

    @property
    def from_address(self) -> str:
        if self.from_name:
            return f"{self.from_name} <{self.username}>"
        return self.username

    @property
    def is_configured(self) -> bool:
        return bool(self.host and self.username)


# ── SMTP ───────────────────────────────────────────────────────────────────────

def test_smtp(config: SmtpConfig) -> str:
    """Return empty string on success, error message on failure."""
    try:
        with smtplib.SMTP(config.host, config.port, timeout=10) as server:
            server.ehlo()
            if config.use_tls:
                server.starttls()
                server.ehlo()
            if config.username and config.password:
                server.login(config.username, config.password)
        return ""
    except Exception as exc:
        return str(exc)


def send_smtp(
    config:    SmtpConfig,
    to:        list[str],
    subject:   str,
    html_body: str,
    cc:        list[str] | None = None,
) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = config.from_address
    msg["To"]      = ", ".join(to)
    if cc:
        msg["Cc"] = ", ".join(cc)
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    recipients = to + (cc or [])
    with smtplib.SMTP(config.host, config.port) as server:
        server.ehlo()
        if config.use_tls:
            server.starttls()
            server.ehlo()
        if config.username and config.password:
            server.login(config.username, config.password)
        server.sendmail(config.username, recipients, msg.as_string())


# ── Outlook COM (Windows only) ─────────────────────────────────────────────────

OUTLOOK_AVAILABLE = sys.platform == "win32"


def send_outlook(
    to:        list[str],
    subject:   str,
    html_body: str,
    cc:        list[str] | None = None,
) -> None:
    if not OUTLOOK_AVAILABLE:
        raise RuntimeError("Outlook COM is only available on Windows.")
    import win32com.client  # type: ignore[import]
    outlook = win32com.client.Dispatch("Outlook.Application")
    mail = outlook.CreateItem(0)   # 0 = olMailItem
    mail.To      = "; ".join(to)
    mail.Subject = subject
    mail.HTMLBody = html_body
    if cc:
        mail.CC = "; ".join(cc)
    mail.Send()


# ── Async worker ───────────────────────────────────────────────────────────────

class SendWorker(QThread):
    """Runs send_smtp / send_outlook off the main thread."""
    success = pyqtSignal()
    error   = pyqtSignal(str)

    def __init__(
        self,
        method:    str,            # "smtp" | "outlook"
        html_body: str,
        to:        list[str],
        subject:   str,
        cc:        list[str],
        config:    SmtpConfig | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._method    = method
        self._html_body = html_body
        self._to        = to
        self._subject   = subject
        self._cc        = cc
        self._config    = config

    def run(self) -> None:
        try:
            if self._method == "outlook":
                send_outlook(self._to, self._subject, self._html_body, self._cc or None)
            else:
                send_smtp(self._config, self._to, self._subject, self._html_body, self._cc or None)
            self.success.emit()
        except Exception as exc:
            self.error.emit(str(exc))

"""Reads and validates the environment.

Deliberately light: os.environ plus python-dotenv, no settings framework. The
deploy script imports this module inside the freshly built image as its "does
the code even load" check, before anything else runs.

Nothing here is ever logged. Values are read, never printed.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:  # optional locally, absent is fine in Docker where env_file is used
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except ImportError:  # pragma: no cover - only hit before deps are installed
    pass


class ConfigError(RuntimeError):
    """Raised when the environment is not usable. Never contains a secret."""


def _optional(key: str, default: str = "") -> str:
    value = os.environ.get(key, "")
    return value.strip() if value.strip() else default


def _int(key: str, default: int) -> int:
    raw = _optional(key)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{key} must be a whole number.") from exc


def _bool(key: str, default: bool = False) -> bool:
    raw = _optional(key).lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes"}


@dataclass(frozen=True)
class Forwarder:
    """One of the three forwarders an enquiry goes to."""

    id: str
    name: str
    email: str


@dataclass(frozen=True)
class Settings:
    # --- runtime ---
    env: str = _optional("APP_ENV", "development")
    port: int = _int("PORT", 8000)
    timezone: str = _optional("TZ", "Asia/Kolkata")
    public_url: str = _optional("PUBLIC_URL", "https://sailing.alokindia.com")

    # --- database ---
    database_url: str = _optional("DATABASE_URL")

    # --- sessions ---
    session_secret: str = _optional("SESSION_SECRET")
    session_cookie: str = _optional("SESSION_COOKIE", "sf_session")
    session_ttl_hours: int = _int("SESSION_TTL_HOURS", 12)

    # --- Google Sheet (read-only) ---
    google_key_path: str = _optional("GOOGLE_KEY_PATH", "/run/secrets/google-key.json")
    sheet_id: str = _optional("SHEET_ID")
    sheet_tab: str = _optional("SHEET_TAB", "all_schedule")

    # --- scheduled jobs (APScheduler, cron syntax, in TZ above) ---
    sync_cron: str = _optional("SYNC_CRON", "0 11 * * *")
    cleanup_cron: str = _optional("CLEANUP_CRON", "30 11 * * *")

    # --- email ---
    smtp_host: str = _optional("SMTP_HOST")
    smtp_port: int = _int("SMTP_PORT", 587)
    smtp_starttls: bool = _bool("SMTP_STARTTLS", True)
    smtp_user: str = _optional("SMTP_USER")
    smtp_pass: str = _optional("SMTP_PASS")
    mail_from: str = _optional("MAIL_FROM", "exports@alokindia.com")
    mail_from_name: str = _optional("MAIL_FROM_NAME", "Alok Ingots (Mumbai) Pvt. Ltd.")
    booking_reply_to: str = _optional("BOOKING_REPLY_TO", "exports@alokindia.com")

    # --- WhatsApp (Interakt) ---
    interakt_api_key: str = _optional("INTERAKT_API_KEY")
    interakt_template: str = _optional("INTERAKT_TEMPLATE_NAME", "sailing_schedule")
    interakt_lang: str = _optional("INTERAKT_TEMPLATE_LANG", "en")
    interakt_country: str = _optional("INTERAKT_COUNTRY_CODE", "91")

    # --- uploads ---
    upload_dir: str = _optional("UPLOAD_DIR", "/app/uploads")
    max_upload_mb: int = _int("MAX_UPLOAD_MB", 15)

    # --- frontend ---
    frontend_dist: str = _optional("FRONTEND_DIST", "/app/frontend_dist")

    forwarders: tuple[Forwarder, ...] = field(default_factory=lambda: _forwarders())

    @property
    def is_production(self) -> bool:
        return self.env == "production"


def _forwarders() -> tuple[Forwarder, ...]:
    """The three forwarders. Each enquiry is emailed to each of them SEPARATELY."""
    found = []
    for n in (1, 2, 3):
        name = _optional(f"FORWARDER_{n}_NAME")
        email = _optional(f"FORWARDER_{n}_EMAIL")
        if name and email:
            found.append(Forwarder(id=f"f{n}", name=name, email=email))
    return tuple(found)


REQUIRED = (
    "DATABASE_URL",
    "SESSION_SECRET",
    "SHEET_ID",
    "GOOGLE_KEY_PATH",
    "SMTP_HOST",
    "SMTP_USER",
    "SMTP_PASS",
    "MAIL_FROM",
)


def validate(s: "Settings") -> None:
    """Fail fast, with a message that names the key but never shows a value."""
    missing = [k for k in REQUIRED if not os.environ.get(k, "").strip()]
    if missing:
        raise ConfigError(
            "Missing required environment variables: "
            + ", ".join(missing)
            + ". Copy backend/.env.example to backend/.env and fill it in."
        )
    if len(s.session_secret) < 32:
        raise ConfigError(
            "SESSION_SECRET must be at least 32 characters. "
            "Generate one with: openssl rand -hex 32"
        )
    if len(s.forwarders) != 3:
        raise ConfigError(
            "All three FORWARDER_n_NAME / FORWARDER_n_EMAIL pairs must be set."
        )


settings = Settings()

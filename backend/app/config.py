"""Reads and validates the environment.

Deliberately light: os.environ plus python-dotenv, no settings framework. The
deploy script imports this module inside the freshly built image as its "does
the code even load" check, before anything else runs.

Nothing here is ever logged. Values are read, never printed.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

try:  # optional locally, absent is fine in Docker where env_file is used
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except ImportError:  # pragma: no cover - only hit before deps are installed
    pass


log = logging.getLogger(__name__)


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


#: FORWARDER_1_*, FORWARDER_2_*, ... are read in order until the first number
#: with neither _NAME nor _EMAIL. This is only a safety ceiling, not a count —
#: add or remove forwarders in .env, no code change.
MAX_FORWARDERS = 100


@dataclass(frozen=True)
class Forwarder:
    """One of the forwarders an enquiry goes to.

    `email` is the To address; `cc` are that same forwarder's other addresses.
    """

    id: str
    name: str
    email: str
    cc: tuple[str, ...] = ()


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

    # --- enquiry email: its own mailbox, separate from the share emails above.
    # Host, port and STARTTLS fall back to the SMTP_* values when not set.
    enquiry_smtp_host: str = _optional("ENQUIRY_SMTP_HOST") or _optional("SMTP_HOST")
    enquiry_smtp_port: int = _int("ENQUIRY_SMTP_PORT", _int("SMTP_PORT", 587))
    enquiry_smtp_starttls: bool = _bool("ENQUIRY_SMTP_STARTTLS", _bool("SMTP_STARTTLS", True))
    enquiry_smtp_user: str = _optional("ENQUIRY_SMTP_USER")
    enquiry_smtp_pass: str = _optional("ENQUIRY_SMTP_PASS")
    enquiry_mail_from: str = _optional("ENQUIRY_MAIL_FROM", "lk.exports@alokindia.com")
    enquiry_mail_from_name: str = _optional(
        "ENQUIRY_MAIL_FROM_NAME", _optional("MAIL_FROM_NAME", "Alok Ingots (Mumbai) Pvt. Ltd.")
    )

    # --- enquiry port of loading: always ours, whatever origin a sailing row
    # carries. The one place the enquiry email and the modal take it from.
    enquiry_origin_port: str = _optional("ENQUIRY_ORIGIN_PORT", "Nhava Sheva")
    enquiry_origin_code: str = _optional("ENQUIRY_ORIGIN_CODE", "INNSA")

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


def _address_list(raw: str) -> tuple[str, ...]:
    """'a@x.com, b@x.com; c@x.com' -> ('a@x.com', 'b@x.com', 'c@x.com')."""
    parts = (p.strip() for p in raw.replace(";", ",").split(","))
    return tuple(dict.fromkeys(p for p in parts if p))


def _forwarder_numbers() -> list[int]:
    """1, 2, 3, ... up to (not including) the first number with neither
    FORWARDER_n_NAME nor FORWARDER_n_EMAIL set."""
    numbers = []
    for n in range(1, MAX_FORWARDERS + 1):
        if not (_optional(f"FORWARDER_{n}_NAME") or _optional(f"FORWARDER_{n}_EMAIL")):
            break
        numbers.append(n)
    return numbers


def _forwarders() -> tuple[Forwarder, ...]:
    """The forwarders, from FORWARDER_n_NAME / _EMAIL (To) / _CC (optional,
    comma-separated). Each enquiry is emailed to each of them SEPARATELY."""
    found = []
    for n in _forwarder_numbers():
        name = _optional(f"FORWARDER_{n}_NAME")
        email = _optional(f"FORWARDER_{n}_EMAIL")
        if name and email:
            cc = tuple(a for a in _address_list(_optional(f"FORWARDER_{n}_CC")) if a != email)
            found.append(Forwarder(id=f"f{n}", name=name, email=email, cc=cc))
    return tuple(found)


def _half_set_forwarders() -> list[int]:
    """Numbers n where only one of FORWARDER_n_NAME / FORWARDER_n_EMAIL is set."""
    return [
        n
        for n in _forwarder_numbers()
        if bool(_optional(f"FORWARDER_{n}_NAME")) != bool(_optional(f"FORWARDER_{n}_EMAIL"))
    ]


def _forwarders_after_a_gap() -> list[int]:
    """Numbers set in the environment but never read, because an earlier
    number is missing (e.g. FORWARDER_5_* with no FORWARDER_4_*)."""
    read = set(_forwarder_numbers())
    pattern = re.compile(r"^FORWARDER_(\d+)_(NAME|EMAIL)$")
    found = {
        int(m.group(1))
        for key, value in os.environ.items()
        if value.strip() and (m := pattern.match(key))
    }
    return sorted(n for n in found if n not in read)


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
    half_set = _half_set_forwarders()
    if half_set:
        raise ConfigError(
            "Each forwarder needs both FORWARDER_n_NAME and FORWARDER_n_EMAIL. "
            "Incomplete: " + ", ".join(f"FORWARDER_{n}" for n in half_set) + "."
        )
    if not s.forwarders:
        raise ConfigError(
            "Set at least one forwarder: FORWARDER_1_NAME and FORWARDER_1_EMAIL "
            "(FORWARDER_1_CC is optional)."
        )
    skipped = _forwarders_after_a_gap()
    if skipped:
        # Not fatal — reading stops at the first missing number by design —
        # but say so, because a renumbering slip would otherwise drop
        # forwarders silently.
        log.warning(
            "Forwarders are read FORWARDER_1 to FORWARDER_%d; ignored after the gap: %s. "
            "Renumber them without gaps to use them.",
            len(_forwarder_numbers()),
            ", ".join(f"FORWARDER_{n}" for n in skipped),
        )


settings = Settings()

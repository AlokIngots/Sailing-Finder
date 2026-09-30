"""Google Sheet (`all_schedule` tab) -> `schedule` table.

Read-only, through a Google service account. The scrapers and the sheet are NOT
touched by this app — we only read what they produce.

Every row is upserted on `row_key`:

    INSERT INTO schedule (...) VALUES (...)
    ON CONFLICT (row_key) DO UPDATE SET ...

so a new sailing is inserted, a changed one updates in place, and nothing is
ever duplicated. There is no truncate-and-reload anywhere: a failed or partial
read must never empty the table. services/cleanup.py runs afterwards to drop
departed sailings.

Rollback for a bad sync: the previous contents of any row that changed are not
kept, so restore from the nightly dump — see deploy.sh. Upcoming sailings cannot
be lost by a sync, only overwritten with fresher values for the same row_key.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime
from typing import Any, Iterable, Sequence

from app import db
from app.config import settings

log = logging.getLogger(__name__)

SCOPES = ("https://www.googleapis.com/auth/spreadsheets.readonly",)

#: Columns of the schedule table, in the documented sheet order. Used as the
#: positional fallback when the header row cannot be matched by name.
COLUMNS: tuple[str, ...] = (
    "carrier",
    "pol_code",
    "pol_name",
    "pod_code",
    "pod_name",
    "vessel_name",
    "voyage_no",
    "etd",
    "eta",
    "transit_days",
    "transshipment",
    "service",
    "source",
    "pulled_on",
    "row_key",
)

DATE_COLUMNS = frozenset({"etd", "eta"})

#: Header spellings seen in the wild, normalised to our column names. Matching
#: by name survives a column being inserted in the middle of the sheet;
#: positional order does not.
HEADER_SYNONYMS: dict[str, str] = {
    "carrier": "carrier",
    "line": "carrier",
    "shippingline": "carrier",
    "polcode": "pol_code",
    "pol": "pol_code",
    "loadport": "pol_name",
    "polname": "pol_name",
    "portofloading": "pol_name",
    "podcode": "pod_code",
    "pod": "pod_code",
    "dischargeport": "pod_name",
    "podname": "pod_name",
    "portofdischarge": "pod_name",
    "port": "pod_name",
    "vessel": "vessel_name",
    "vesselname": "vessel_name",
    "voyage": "voyage_no",
    "voyageno": "voyage_no",
    "voy": "voyage_no",
    "etd": "etd",
    "departs": "etd",
    "departure": "etd",
    "sailingdate": "etd",
    "eta": "eta",
    "arrives": "eta",
    "arrival": "eta",
    "transit": "transit_days",
    "transitdays": "transit_days",
    "transittime": "transit_days",
    "transshipment": "transshipment",
    "transhipment": "transshipment",
    "ts": "transshipment",
    "service": "service",
    "servicename": "service",
    "source": "source",
    "pulledon": "pulled_on",
    "scrapedon": "pulled_on",
    "rowkey": "row_key",
    "key": "row_key",
}

#: Tried in order. Day-first is listed before month-first because the scrapers
#: and the team both write dates day-first; an ambiguous 05/06/2026 is read as
#: 5 June, not 6 May.
DATE_FORMATS = (
    "%Y-%m-%d",
    "%d %b %Y",
    "%d %B %Y",
    "%d-%b-%Y",
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%d.%m.%Y",
    "%Y/%m/%d",
)


class SheetSyncError(RuntimeError):
    """Something went wrong reading the sheet. Never carries a credential."""


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------
def _normalise_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def map_headers(header_row: Sequence[str]) -> dict[str, int]:
    """Column name -> index, from the sheet's own header row."""
    mapping: dict[str, int] = {}
    for index, raw in enumerate(header_row):
        key = _normalise_header(raw)
        column = HEADER_SYNONYMS.get(key) or (key if key in COLUMNS else None)
        if column and column not in mapping:
            mapping[column] = index
    return mapping


def parse_date(value: Any) -> date | None:
    """A sheet date in any of the shapes the scrapers produce, or None."""
    if value in (None, ""):
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()

    text = str(value).strip()
    if not text:
        return None

    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue

    log.warning("unrecognised date %r — left empty", text[:40])
    return None


def parse_int(value: Any) -> int | None:
    digits = re.sub(r"[^0-9-]", "", str(value or ""))
    if digits in ("", "-"):
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def make_row_key(row: dict) -> str:
    """Fallback identity for a sailing when the sheet has no row_key.

    Deliberately the things that make a sailing *that* sailing. If any of them
    change it is a different row, which is the safe way round: a stale duplicate
    is visible, a wrongly-merged row is not.
    """
    parts = (
        row.get("carrier"),
        row.get("pol_code"),
        row.get("pod_code"),
        row.get("vessel_name"),
        row.get("voyage_no"),
        row["etd"].isoformat() if row.get("etd") else "",
    )
    return "|".join(str(p or "").strip().upper() for p in parts)


def parse_rows(values: Sequence[Sequence[Any]]) -> list[dict]:
    """Sheet values (header row first) -> rows ready for the database."""
    if not values:
        return []

    header, *body = values
    mapping = map_headers(header)

    if len(mapping) < 5:
        # The header did not look like ours. Fall back to the documented column
        # order rather than importing nonsense.
        log.warning(
            "sheet header not recognised (%s matched) — falling back to column order",
            len(mapping),
        )
        mapping = {name: i for i, name in enumerate(COLUMNS)}
        body = values  # no header row to skip

    rows: list[dict] = []
    skipped = 0

    for raw in body:
        row: dict[str, Any] = {}
        for column, index in mapping.items():
            cell = raw[index] if index < len(raw) else None
            if column in DATE_COLUMNS:
                row[column] = parse_date(cell)
            elif column == "transit_days":
                row[column] = parse_int(cell)
            elif column == "pulled_on":
                row[column] = parse_date(cell)
            else:
                row[column] = (str(cell).strip() if cell is not None else "")

        for column in COLUMNS:
            row.setdefault(column, None)

        # A sailing with no departure date cannot be filtered, sorted or cleaned
        # up, so it is no use to anyone.
        if not row.get("etd"):
            skipped += 1
            continue

        if not row.get("row_key"):
            row["row_key"] = make_row_key(row)

        rows.append(row)

    if skipped:
        log.warning("skipped %s row(s) with no usable departure date", skipped)

    return rows


# ---------------------------------------------------------------------------
# Google
# ---------------------------------------------------------------------------
def read_sheet() -> list[list[Any]]:
    """Raw values from the `all_schedule` tab."""
    try:
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build
    except ImportError as exc:  # pragma: no cover
        raise SheetSyncError("Google client libraries are not installed.") from exc

    try:
        credentials = Credentials.from_service_account_file(
            settings.google_key_path, scopes=list(SCOPES)
        )
    except FileNotFoundError as exc:
        raise SheetSyncError(
            f"Service-account key not found at {settings.google_key_path}. "
            "Check GOOGLE_KEY_PATH and the docker-compose mount."
        ) from exc

    service = build("sheets", "v4", credentials=credentials, cache_discovery=False)
    response = (
        service.spreadsheets()
        .values()
        .get(
            spreadsheetId=settings.sheet_id,
            range=f"{settings.sheet_tab}!A:O",
            valueRenderOption="UNFORMATTED_VALUE",
            dateTimeRenderOption="FORMATTED_STRING",
        )
        .execute()
    )
    return response.get("values", [])


# ---------------------------------------------------------------------------
# Upsert
# ---------------------------------------------------------------------------
UPSERT = """
INSERT INTO schedule (
    carrier, pol_code, pol_name, pod_code, pod_name, vessel_name, voyage_no,
    etd, eta, transit_days, transshipment, service, source, pulled_on, row_key
) VALUES (
    %(carrier)s, %(pol_code)s, %(pol_name)s, %(pod_code)s, %(pod_name)s,
    %(vessel_name)s, %(voyage_no)s, %(etd)s, %(eta)s, %(transit_days)s,
    %(transshipment)s, %(service)s, %(source)s, %(pulled_on)s, %(row_key)s
)
ON CONFLICT (row_key) DO UPDATE SET
    carrier       = EXCLUDED.carrier,
    pol_code      = EXCLUDED.pol_code,
    pol_name      = EXCLUDED.pol_name,
    pod_code      = EXCLUDED.pod_code,
    pod_name      = EXCLUDED.pod_name,
    vessel_name   = EXCLUDED.vessel_name,
    voyage_no     = EXCLUDED.voyage_no,
    etd           = EXCLUDED.etd,
    eta           = EXCLUDED.eta,
    transit_days  = EXCLUDED.transit_days,
    transshipment = EXCLUDED.transshipment,
    service       = EXCLUDED.service,
    source        = EXCLUDED.source,
    pulled_on     = EXCLUDED.pulled_on
"""


def upsert_rows(rows: Iterable[dict]) -> int:
    """Insert or update every row, in one transaction. Returns how many."""
    rows = list(rows)
    if not rows:
        return 0

    with db.connection() as conn, conn.cursor() as cur:
        cur.executemany(UPSERT, rows)

    return len(rows)


def sync_schedule_from_sheet() -> dict:
    """Read the sheet and upsert every row. Returns counts for the job log."""
    values = read_sheet()
    if not values:
        # An empty read is almost certainly a permissions or tab-name problem.
        # Treat it as an error: doing nothing is right, but doing it silently is
        # how a stale schedule goes unnoticed for a week.
        raise SheetSyncError(
            f"Sheet {settings.sheet_id} tab {settings.sheet_tab!r} returned no rows."
        )

    rows = parse_rows(values)
    if not rows:
        raise SheetSyncError("Sheet had rows but none of them were usable sailings.")

    written = upsert_rows(rows)
    log.info("synced %s sailing(s) from the sheet", written)
    return {"read": len(values) - 1, "written": written}

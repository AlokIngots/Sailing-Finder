"""Google Sheet (`all_schedule` tab) -> `schedule` table.

Read-only, via a Google service account. The scrapers and the sheet are NOT
touched by this app — we only read what they produce.

Every row is upserted:

    INSERT INTO schedule (...) VALUES (...)
    ON CONFLICT (row_key) DO UPDATE SET ...

so a new sailing is inserted, a changed one updates in place, and nothing is
ever duplicated. There is no truncate-and-reload anywhere — a failed read must
never empty the table.

services/cleanup.py runs afterwards to drop departed sailings.

SCAFFOLD: not implemented. Built on feature/sheet-sync, once the exact column
order of `all_schedule` is confirmed against the live sheet.
"""

from __future__ import annotations

import logging

from app.config import settings

log = logging.getLogger(__name__)

SCOPES = ("https://www.googleapis.com/auth/spreadsheets.readonly",)

#: Columns of the schedule table, in sheet order.
COLUMNS = (
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


def sync_schedule_from_sheet() -> dict:
    """Read the sheet and upsert every row. Returns counts."""
    raise NotImplementedError(
        f"sheet_sync is not built yet (sheet {settings.sheet_id}, tab {settings.sheet_tab})."
    )

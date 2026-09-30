"""Freshness / auto-delete for the `schedule` table.

The scrapers' Google Sheet self-cleans: only today and future sailings stay in
it. This reproduces that in our own database, so the app can never show a ship
that has already left.

    DELETE FROM schedule WHERE etd < CURRENT_DATE;

Safety, in this order, every time:
  1. copy the rows about to go into a timestamped bk_schedule_<stamp> table
  2. delete ONLY rows whose etd is genuinely in the past
  3. never a wipe-and-reload, so a bad sync cannot lose upcoming sailings

Rollback after a bad run:
    INSERT INTO schedule SELECT * FROM bk_schedule_<stamp>
    ON CONFLICT (row_key) DO NOTHING;

Runs at the end of every sync, and again as a daily job (jobs/daily.py).
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta

from app import db

log = logging.getLogger(__name__)

KEEP_BACKUP_DAYS = 7
_BACKUP_PREFIX = "bk_schedule_"
_STAMP_RE = re.compile(r"^\d{8}_\d{6}$")


def _stamp(now: datetime) -> str:
    return now.strftime("%Y%m%d_%H%M%S")


def cleanup_departed_sailings(now: datetime | None = None) -> dict:
    """Back up, then delete departed sailings. Returns what it did."""
    now = now or datetime.now()

    with db.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) AS n FROM schedule WHERE etd < CURRENT_DATE")
        doomed = cur.fetchone()["n"]

        if doomed == 0:
            log.info("nothing to remove — no sailings with etd before today")
            return {"deleted": 0, "backup_table": None}

        # The table name is built from a timestamp we generate, never from user
        # input, and is checked against _STAMP_RE before use.
        stamp = _stamp(now)
        assert _STAMP_RE.match(stamp)
        backup_table = f"{_BACKUP_PREFIX}{stamp}"

        cur.execute(
            f'CREATE TABLE "{backup_table}" AS '  # noqa: S608 - identifier is generated, not user input
            "SELECT * FROM schedule WHERE etd < CURRENT_DATE"
        )
        cur.execute("DELETE FROM schedule WHERE etd < CURRENT_DATE")
        deleted = cur.rowcount

    log.info(
        "removed %s departed sailing(s); backup in %s. Rollback: "
        "INSERT INTO schedule SELECT * FROM %s ON CONFLICT (row_key) DO NOTHING;",
        deleted,
        backup_table,
        backup_table,
    )
    return {"deleted": deleted, "backup_table": backup_table}


def prune_old_backups(now: datetime | None = None) -> int:
    """Drop bk_schedule_* tables older than KEEP_BACKUP_DAYS."""
    now = now or datetime.now()
    cutoff = (now - timedelta(days=KEEP_BACKUP_DAYS)).strftime("%Y%m%d")

    rows = db.fetch_all(
        """
        SELECT tablename FROM pg_tables
         WHERE schemaname = 'public'
           AND tablename LIKE %s
        """,
        (_BACKUP_PREFIX.replace("_", r"\_") + "%",),
    )

    dropped = 0
    for row in rows:
        name = row["tablename"]
        stamp = name[len(_BACKUP_PREFIX) :]
        if _STAMP_RE.match(stamp) and stamp[:8] < cutoff:
            db.execute(f'DROP TABLE IF EXISTS "{name}"')  # noqa: S608 - name matched _STAMP_RE
            dropped += 1

    if dropped:
        log.info("pruned %s backup table(s) older than %s days", dropped, KEEP_BACKUP_DAYS)
    return dropped

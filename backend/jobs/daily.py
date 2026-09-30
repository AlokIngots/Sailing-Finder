"""Daily job: pull the sheet into the schedule table, then drop departed sailings.

    python -m jobs.daily            run once, now
    python -m jobs.daily --schedule stay resident on SYNC_CRON / CLEANUP_CRON

Order matters. Sync first so today's new sailings are in, cleanup second so
anything that has already left goes out. Cleanup backs up before it deletes —
see app/services/cleanup.py for the rollback command.
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from apscheduler.schedulers.blocking import BlockingScheduler  # noqa: E402
from apscheduler.triggers.cron import CronTrigger  # noqa: E402

from app import db  # noqa: E402
from app.config import settings  # noqa: E402
from app.services.cleanup import cleanup_departed_sailings, prune_old_backups  # noqa: E402
from app.services.sheet_sync import sync_schedule_from_sheet  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [daily] %(message)s")
log = logging.getLogger(__name__)


def run_sync() -> None:
    try:
        result = sync_schedule_from_sheet()
        log.info("sync done: %s", result)
    except Exception as exc:  # noqa: BLE001
        # A failed sync must NOT stop the cleanup, and must never empty the table.
        log.error("sync FAILED — schedule table left as it was: %s", exc)


def run_cleanup() -> None:
    try:
        cleanup_departed_sailings()
        prune_old_backups()
    except Exception as exc:  # noqa: BLE001
        log.error("cleanup FAILED: %s", exc)


def run_once() -> None:
    started = time.monotonic()
    run_sync()
    run_cleanup()
    log.info("finished in %.0fs", time.monotonic() - started)


def main() -> None:
    db.open_pool()
    try:
        if "--schedule" in sys.argv:
            sched = BlockingScheduler(timezone=settings.timezone)
            sched.add_job(run_once, CronTrigger.from_crontab(settings.sync_cron), id="sync")
            sched.add_job(run_cleanup, CronTrigger.from_crontab(settings.cleanup_cron), id="cleanup")
            log.info(
                "scheduled: sync %s, cleanup %s (%s)",
                settings.sync_cron,
                settings.cleanup_cron,
                settings.timezone,
            )
            sched.start()
        else:
            run_once()
    finally:
        db.close_pool()


if __name__ == "__main__":
    main()

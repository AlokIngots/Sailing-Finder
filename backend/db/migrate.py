"""Applies db/schema.sql. Safe to re-run — every statement is idempotent.

    python -m db.migrate          (from backend/, inside the container)

./deploy.sh runs this automatically, before the app starts.

This never drops or alters existing data. Any future change that DOES touch
existing data gets its own reviewed migration with a stated rollback, and a
table dump taken first — see CONTRIBUTING.md.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import db  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s [migrate] %(message)s")
log = logging.getLogger(__name__)


def main() -> int:
    schema = Path(__file__).with_name("schema.sql")
    sql = schema.read_text(encoding="utf-8")
    log.info("applying %s", schema)

    db.open_pool()
    try:
        # One transaction: either the whole schema applies or none of it does.
        with db.connection() as conn, conn.cursor() as cur:
            cur.execute(sql)
        log.info("OK")
        return 0
    except Exception as exc:  # noqa: BLE001 - reported, not re-raised
        log.error("FAILED — nothing was applied: %s", exc)
        return 1
    finally:
        db.close_pool()


if __name__ == "__main__":
    raise SystemExit(main())

"""Load a sample schedule so the finder can be run and looked at locally.

There is no Google service-account key on a developer machine, so
services/sheet_sync.py cannot run. This fills the `schedule` table with
plausible, entirely made-up sailings instead.

    python -m scripts.seed_sample              # ~180 sailings over 8 weeks
    python -m scripts.seed_sample --count 400
    python -m scripts.seed_sample --clear      # remove them again

NOTHING HERE IS REAL. The vessels, voyage numbers and dates are generated from a
fixed seed; the carriers and ports are public names only. No customer, rate or
booking data appears in this file or in what it writes — and it must stay that
way, because this script is committed.

Every row is written with source = 'sample-seed', and --clear only ever deletes
rows carrying that marker, so running this against a database that holds real
sailings cannot remove them.

Rollback:
    DELETE FROM schedule WHERE source = 'sample-seed';
"""

from __future__ import annotations

import argparse
import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import db  # noqa: E402
from app.services.sheet_sync import upsert_rows  # noqa: E402

SOURCE = "sample-seed"
SEED = 20260930  # fixed, so two people seeding get the same list

CARRIERS = ("MSC", "ONE", "HMM", "CMA CGM", "MAERSK", "HAPAG-LLOYD", "TURKON", "SCI")

#: (code, name) — real ports, because the country filter derives from the
#: LOCODE prefix and nonsense codes would make the dropdown nonsense too.
LOAD_PORTS = (
    ("INNSA", "Nhava Sheva"),
    ("INMUN", "Mundra"),
    ("INPAV", "Pipavav"),
)

DISCHARGE_PORTS = (
    ("NLRTM", "Rotterdam"),
    ("BEANR", "Antwerp"),
    ("DEHAM", "Hamburg"),
    ("GBFXT", "Felixstowe"),
    ("ESVLC", "Valencia"),
    ("ITGOA", "Genoa"),
    ("GRPIR", "Piraeus"),
    ("TRMER", "Mersin"),
    ("TRIST", "Istanbul"),
    ("EGALY", "Alexandria"),
    ("AEJEA", "Jebel Ali"),
    ("SADMM", "Dammam"),
    ("USNYC", "New York"),
    ("USHOU", "Houston"),
    ("BRSSZ", "Santos"),
    ("ZADUR", "Durban"),
    ("KEMBA", "Mombasa"),
    ("SGSIN", "Singapore"),
    ("MYPKG", "Port Klang"),
    ("AUSYD", "Sydney"),
)

VESSEL_PREFIXES = ("MSC", "ONE", "NORTHERN", "CAPE", "MAERSK", "EXPRESS", "AS", "BLUE")
VESSEL_NAMES = (
    "ARIES", "BOREAS", "CASSIOPEIA", "DIAMOND", "ENDEAVOUR", "FORTUNA",
    "GEMINI", "HORIZON", "INDUS", "JUPITER", "KESTREL", "LYRA",
    "MERIDIAN", "NEPTUNE", "ORION", "PEGASUS", "QUASAR", "RIGEL",
    "SIRIUS", "TITAN", "VEGA", "ZEPHYR",
)

SERVICES = ("INDAMEX", "MIDAS", "EPIC", "BEX", "WIN", "SIRIUS", "")

#: Roughly what the sheet looks like: mostly direct, a fair number of one-stop,
#: a few two-stop, and a handful the scrapers could not label at all.
TRANSSHIPMENT_MIX = ("0", "0", "0", "0", "1", "1", "1", "2", "", "")


def build_rows(count: int, today: date, rng: random.Random) -> list[dict]:
    rows: list[dict] = []
    seen: set[str] = set()
    pulled_on = datetime.combine(today, datetime.min.time())

    while len(rows) < count:
        carrier = rng.choice(CARRIERS)
        pol_code, pol_name = rng.choice(LOAD_PORTS)
        pod_code, pod_name = rng.choice(DISCHARGE_PORTS)

        vessel = f"{rng.choice(VESSEL_PREFIXES)} {rng.choice(VESSEL_NAMES)}"
        voyage = f"{rng.randint(100, 399)}{rng.choice('AEWS')}"

        # Departures spread over the next eight weeks, including today, so the
        # "Leaving soon" badge and the date filters both have something to bite.
        etd = today + timedelta(days=rng.randint(0, 56))

        transshipment = rng.choice(TRANSSHIPMENT_MIX)
        # Indirect sailings take longer; that is the whole reason to filter on it.
        base = {"INNSA": 0, "INMUN": 1, "INPAV": 2}.get(pol_code, 0)
        legs = int(transshipment) if transshipment.isdigit() else 1
        transit_days = rng.randint(14, 42) + base + legs * rng.randint(3, 8)
        eta = etd + timedelta(days=transit_days)

        row_key = f"{carrier}|{pol_code}|{pod_code}|{vessel}|{voyage}|{etd.isoformat()}"
        if row_key in seen:
            continue
        seen.add(row_key)

        rows.append(
            {
                "carrier": carrier,
                "pol_code": pol_code,
                "pol_name": pol_name,
                "pod_code": pod_code,
                "pod_name": pod_name,
                "vessel_name": vessel,
                "voyage_no": voyage,
                "etd": etd,
                "eta": eta,
                "transit_days": transit_days,
                "transshipment": transshipment,
                "service": rng.choice(SERVICES),
                "source": SOURCE,
                "pulled_on": pulled_on,
                "row_key": row_key,
            }
        )

    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed sample sailings for local use.")
    parser.add_argument("--count", type=int, default=180, help="how many sailings")
    parser.add_argument(
        "--clear",
        action="store_true",
        help="delete previously seeded sample rows and stop",
    )
    args = parser.parse_args()

    db.open_pool()
    try:
        if args.clear:
            removed = db.execute("DELETE FROM schedule WHERE source = %s", (SOURCE,))
            print(f"Removed {removed} sample sailing(s).")
            return 0

        if args.count < 1:
            print("--count must be at least 1.", file=sys.stderr)
            return 1

        rows = build_rows(args.count, date.today(), random.Random(SEED))
        written = upsert_rows(rows)
        print(
            f"Seeded {written} sample sailing(s), source='{SOURCE}'.\n"
            f"Remove them again with: python -m scripts.seed_sample --clear"
        )
        return 0
    finally:
        db.close_pool()


if __name__ == "__main__":
    raise SystemExit(main())

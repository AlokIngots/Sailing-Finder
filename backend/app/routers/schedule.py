"""The sailing schedule.

Read from the `schedule` table only — never from the Google Sheet directly. The
sheet reaches the table through services/sheet_sync.py.

Filtering and sorting happen in SQL rather than in the browser. The share
endpoints have to rebuild the exact list the user is looking at, server-side,
before attaching it to an email or a PDF — so the rules live here, once.
"""

from __future__ import annotations

import logging
import re
from datetime import date
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app import db
from app.deps import CurrentUser, require_auth
from app.services import ports

log = logging.getLogger(__name__)

router = APIRouter()

#: Every schedule query is bounded. The table only ever holds today + future
#: sailings, so this is headroom rather than a real ceiling.
MAX_ROWS = 2000

COLUMNS = (
    "row_key",
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
)

#: Direct / Indirect, matching reference/Index.html's shipType():
#:
#:     var n = parseFloat(s); if (isNaN(n)) return ""; return n === 0 ? "direct" : "indirect";
#:
#: parseFloat reads a leading number and ignores whatever follows, so "1 (SIN)"
#: is one transshipment and "1.5" is a fraction of one — both indirect. Only a
#: value that does not start with a number at all is unlabelled, and unlabelled
#: sailings appear solely under "All".
#:
#: This regex is that rule: an optional sign, then digits with an optional
#: fractional part. substring() returns the first parenthesised group, so the
#: sign is kept. ship_type() below applies the identical rule in Python, so what
#: the filter selects and what the row is tagged as can never disagree.
_LEADING_NUMBER_SQL = (
    r"substring(btrim(coalesce(transshipment, '')) from '^([+-]?(?:[0-9]+\.?[0-9]*|\.[0-9]+))')"
)
_DIRECT_SQL = f"({_LEADING_NUMBER_SQL} IS NOT NULL AND {_LEADING_NUMBER_SQL}::numeric = 0)"
_INDIRECT_SQL = f"({_LEADING_NUMBER_SQL} IS NOT NULL AND {_LEADING_NUMBER_SQL}::numeric <> 0)"

#: The Python half of the rule above.
_LEADING_NUMBER = re.compile(r"^[+-]?(?:\d+\.?\d*|\.\d+)")

SORTS = {
    "etd": "etd ASC NULLS LAST, eta ASC NULLS LAST",              # soonest departure
    "transit": "transit_days ASC NULLS LAST, etd ASC NULLS LAST",  # fastest transit
    "eta": "eta ASC NULLS LAST, etd ASC NULLS LAST",               # soonest arrival
}


def ship_type(transshipment: str | None) -> str:
    """'direct' | 'indirect' | 'unlabelled', matching the reference's shipType()."""
    match = _LEADING_NUMBER.match((transshipment or "").strip())
    if not match:
        return "unlabelled"
    return "direct" if float(match.group()) == 0 else "indirect"


def build_schedule_query(
    *,
    country: str | None = None,
    pod_code: str | None = None,
    carrier: str | None = None,
    etd_from: date | None = None,
    etd_to: date | None = None,
    eta_from: date | None = None,
    eta_to: date | None = None,
    routing: str = "all",
    mode: str = "all",
    sort: str = "etd",
    limit: int = MAX_ROWS,
) -> tuple[str, list[Any]]:
    """Turn the finder's filter state into one parameterised query.

    Split out from the endpoint so the filter rules can be tested without a
    database. Every value is bound as a parameter; nothing is interpolated.
    """
    where: list[str] = ["etd >= CURRENT_DATE"]  # a departed sailing is never useful
    params: list[Any] = []

    if country:
        # A LOCODE starts with the ISO country code, so a country filter is a
        # prefix match on the POD. See services/ports.py.
        iso = ports.iso_for_country(country)
        if not iso:
            # Unknown country: match nothing, rather than silently ignoring it
            # and showing the world.
            where.append("FALSE")
        else:
            where.append("upper(pod_code) LIKE %s")
            params.append(f"{iso}%")

    if pod_code:
        where.append("upper(pod_code) = %s")
        params.append(pod_code.strip().upper())

    if carrier:
        where.append("carrier = %s")
        params.append(carrier.strip())

    for column, value, op in (
        ("etd", etd_from, ">="),
        ("etd", etd_to, "<="),
        ("eta", eta_from, ">="),
        ("eta", eta_to, "<="),
    ):
        if value is not None:
            if column == "eta":
                # The reference skips the arrival test when a sailing has no ETA
                # (`if(af && r.eta && r.eta < af)`), so a carrier that published
                # no arrival date is not silently filtered out of the list.
                where.append(f"(eta IS NULL OR eta {op} %s)")
            else:
                where.append(f"etd {op} %s")
            params.append(value)

    if routing == "direct":
        where.append(_DIRECT_SQL)
    elif routing == "indirect":
        where.append(_INDIRECT_SQL)

    columns = ", ".join(COLUMNS)
    order_by = SORTS.get(sort, SORTS["etd"])
    where_sql = " AND ".join(where)

    if mode == "next_per_port":
        # The soonest departure to each port BY EACH CARRIER — the reference
        # keys on `r.pod_code + "|" + r.carrier`, not the port alone, so a
        # customer still sees every line that serves the port, just once each.
        # The inner ORDER BY is what DISTINCT ON picks by, so it is fixed; the
        # user's sort is applied to the result.
        sql = (
            f"SELECT * FROM ("
            f"  SELECT DISTINCT ON (pod_code, carrier) {columns}"
            f"    FROM schedule"
            f"   WHERE {where_sql}"
            f"   ORDER BY pod_code, carrier, etd ASC NULLS LAST, eta ASC NULLS LAST"
            f") next_per_port"
            f" ORDER BY {order_by}"
            f" LIMIT %s"
        )
    else:
        sql = (
            f"SELECT {columns}"
            f"  FROM schedule"
            f" WHERE {where_sql}"
            f" ORDER BY {order_by}"
            f" LIMIT %s"
        )

    params.append(min(int(limit), MAX_ROWS))
    return sql, params


def shape(row: dict) -> dict:
    """One sailing, as the browser wants it.

    `country` and `ship_type` are derived here so that the finder, the CSV, the
    PDF and the emails all describe a sailing the same way.
    """
    return {
        "row_key": row["row_key"],
        "carrier": row["carrier"] or "",
        "pol_code": row["pol_code"] or "",
        "pol_name": row["pol_name"] or "",
        "pod_code": row["pod_code"] or "",
        "pod_name": row["pod_name"] or "",
        "country": ports.country_for_port(row["pod_code"]),
        "vessel_name": row["vessel_name"] or "",
        "voyage_no": row["voyage_no"] or "",
        "etd": row["etd"].isoformat() if row["etd"] else None,
        "eta": row["eta"].isoformat() if row["eta"] else None,
        "transit_days": row["transit_days"],
        "transshipment": row["transshipment"] or "",
        "ship_type": ship_type(row["transshipment"]),
        "service": row["service"] or "",
    }


@router.get("/schedule")
def get_schedule(
    user: CurrentUser = Depends(require_auth),
    country: str | None = None,
    pod_code: str | None = None,
    carrier: str | None = None,
    etd_from: date | None = None,
    etd_to: date | None = None,
    eta_from: date | None = None,
    eta_to: date | None = None,
    routing: Literal["all", "direct", "indirect"] = "all",
    mode: Literal["all", "next_per_port"] = "all",
    sort: Literal["etd", "transit", "eta"] = "etd",
    limit: int = Query(default=MAX_ROWS, ge=1, le=MAX_ROWS),
) -> dict:
    """Filtered sailings, newest departure first unless told otherwise."""
    sql, params = build_schedule_query(
        country=country,
        pod_code=pod_code,
        carrier=carrier,
        etd_from=etd_from,
        etd_to=etd_to,
        eta_from=eta_from,
        eta_to=eta_to,
        routing=routing,
        mode=mode,
        sort=sort,
        limit=limit,
    )
    rows = db.fetch_all(sql, params)

    return {
        "status": "ok",
        "data": {
            "rows": [shape(r) for r in rows],
            "count": len(rows),
            "truncated": len(rows) >= min(limit, MAX_ROWS),
        },
        "message": "",
    }


@router.get("/schedule/filters")
def get_filters(
    user: CurrentUser = Depends(require_auth),
    country: str | None = None,
) -> dict:
    """Options for the cascading dropdowns.

    Countries and carriers come from the whole table; ports narrow to the
    selected country, which is what makes Country -> Port cascade. Options are
    built from the data that is actually there, so a port with no sailings never
    appears and then returns nothing.
    """
    rows = db.fetch_all(
        """
        SELECT DISTINCT pod_code, pod_name, carrier
          FROM schedule
         WHERE etd >= CURRENT_DATE
        """
    )

    iso = ports.iso_for_country(country) if country else ""

    seen_ports: dict[str, str] = {}
    for row in rows:
        code = (row["pod_code"] or "").strip().upper()
        if not code:
            continue
        if iso and not code.startswith(iso):
            continue
        # First non-empty name wins; codes are the key, so a port cannot appear
        # twice because one scraper spells its name differently.
        seen_ports.setdefault(code, (row["pod_name"] or code).strip() or code)

    return {
        "status": "ok",
        "data": {
            "countries": ports.country_options(r["pod_code"] for r in rows),
            "ports": [
                {"code": code, "name": name}
                for code, name in sorted(seen_ports.items(), key=lambda kv: kv[1])
            ],
            "carriers": sorted({(r["carrier"] or "").strip() for r in rows} - {""}),
        },
        "message": "",
    }


@router.get("/forwarders")
def get_forwarders(user: CurrentUser = Depends(require_auth)):
    """Names only. The addresses stay server-side and never reach the browser.

    Built on feature/enquiry — the finder does not need it.
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Forwarders is not built yet.",
    )

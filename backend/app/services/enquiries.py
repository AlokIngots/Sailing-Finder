"""Enquiry tracking — the `enquiries`, `enquiry_quotes` and
`enquiry_rate_history` tables.

Who sees what is decided HERE, in SQL: a normal user's queries carry
`AND e.created_by = %s`, an admin's do not. Same rule as My bookings. The
React app never filters.

Every statement is parameterised. The only text spliced into SQL is the fixed
scope fragment below, never anything a user typed.
"""

from __future__ import annotations

from app import db
from app.deps import CurrentUser
from app.services.enquiry_email import tidy_vessel

REF_PREFIX = "ENQ-"

#: The list is bounded; newest first.
MAX_LIST = 500

_ENQUIRY_COLUMNS = (
    "e.id, e.ref, e.vessel, e.voyage, e.carrier, e.pod_name, e.country, e.etd, e.eta, "
    "e.transit_days, e.stuffing_date, e.containers, e.net_weight, e.gross_weight, "
    "e.commodity, e.remarks, e.created_by, e.created_at, e.status, e.winner_quote_id"
)


class AlreadyBooked(Exception):
    """The winner of a booked enquiry cannot be changed."""


def _scope(user: CurrentUser) -> tuple[str, tuple]:
    """(SQL fragment, params) limiting `e` to what this user may see."""
    if user.is_admin:
        return "", ()
    return " AND e.created_by = %s", (user.username,)


def next_ref() -> str:
    """A new, never-reused ref: ENQ-0001, ENQ-0002, ...

    Taken BEFORE the email goes out, because the ref is in its subject. A
    number whose send then fails entirely is simply skipped.
    """
    row = db.fetch_one("SELECT nextval('enquiry_ref_seq') AS n")
    return f"{REF_PREFIX}{row['n']:04d}"


def record(ref: str, sailing: dict, fields, username: str, forwarders) -> None:
    """Write the enquiry (status 'sent') and one quote row per forwarder it
    reached — in one transaction, so there is never an enquiry without them.

    `sailing` is a shaped schedule row (routers.schedule.shape); `fields` is
    the modal (routers.bookings.EnquiryIn).
    """
    vessel, voyage = tidy_vessel(sailing)
    with db.connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO enquiries (
              ref, vessel, voyage, carrier, pod_name, country, etd, eta, transit_days,
              stuffing_date, containers, net_weight, gross_weight, commodity, remarks,
              created_by, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'sent')
            RETURNING id
            """,
            (
                ref,
                vessel,
                voyage,
                sailing.get("carrier") or "",
                sailing.get("pod_name") or sailing.get("pod_code") or "",
                sailing.get("country") or "",
                sailing.get("etd"),
                sailing.get("eta"),
                sailing.get("transit_days"),
                fields.stuffing,
                fields.container,
                fields.net_wt,
                fields.gross_wt,
                fields.commodity,
                fields.remarks,
                username,
            ),
        )
        enquiry_id = cur.fetchone()["id"]
        for forwarder in forwarders:
            cur.execute(
                "INSERT INTO enquiry_quotes (enquiry_id, forwarder_name, forwarder_email) "
                "VALUES (%s, %s, %s)",
                (enquiry_id, forwarder.name, forwarder.email),
            )


def list_for(user: CurrentUser, limit: int = MAX_LIST) -> list[dict]:
    """The enquiries this user may see, newest first."""
    scope, params = _scope(user)
    return db.fetch_all(
        f"SELECT {_ENQUIRY_COLUMNS} FROM enquiries e WHERE TRUE{scope} "
        "ORDER BY e.created_at DESC, e.id DESC LIMIT %s",
        (*params, min(max(limit, 1), MAX_LIST)),
    )


def list_with_quotes(user: CurrentUser, limit: int = MAX_LIST) -> list[dict]:
    """list_for(), each enquiry carrying its quotes (one per forwarder it was
    sent to) — the rate summary. Two queries, not one per enquiry."""
    rows = list_for(user, limit)
    if not rows:
        return rows
    quotes = db.fetch_all(
        "SELECT q.id, q.enquiry_id, q.forwarder_name, q.quoted_rate "
        "FROM enquiry_quotes q WHERE q.enquiry_id = ANY(%s) ORDER BY q.id",
        ([r["id"] for r in rows],),
    )
    by_enquiry: dict[int, list[dict]] = {}
    for q in quotes:
        by_enquiry.setdefault(q["enquiry_id"], []).append(q)
    for row in rows:
        row["quotes"] = by_enquiry.get(row["id"], [])
    return rows


def get(ref: str, user: CurrentUser) -> dict | None:
    """One enquiry with its quotes, or None when it does not exist OR this
    user may not see it — the two are indistinguishable on purpose."""
    scope, params = _scope(user)
    enquiry = db.fetch_one(
        f"SELECT {_ENQUIRY_COLUMNS} FROM enquiries e WHERE e.ref = %s{scope}",
        (ref, *params),
    )
    if not enquiry:
        return None
    enquiry["quotes"] = db.fetch_all(
        "SELECT q.id, q.forwarder_name, q.replied_at, q.quoted_rate, q.notes, q.updated_at "
        "FROM enquiry_quotes q WHERE q.enquiry_id = %s ORDER BY q.id",
        (enquiry["id"],),
    )
    return enquiry


def _locked_quote(cur, ref: str, quote_id: int, user: CurrentUser) -> dict | None:
    """The quote and its enquiry, row-locked, if this user may see them."""
    scope, params = _scope(user)
    cur.execute(
        "SELECT q.id, q.quoted_rate, q.notes, e.id AS enquiry_id, e.status "
        "FROM enquiry_quotes q JOIN enquiries e ON e.id = q.enquiry_id "
        f"WHERE e.ref = %s AND q.id = %s{scope} FOR UPDATE OF q, e",
        (ref, quote_id, *params),
    )
    return cur.fetchone()


def update_quote(ref: str, quote_id: int, user: CurrentUser, *, rate=None, notes=None) -> bool:
    """Save a quote's rate and/or notes (None = leave as is; '' = clear).

    A changed rate appends the rate it had before to enquiry_rate_history. The
    first rate on a 'sent' enquiry moves it to 'quoting'. False when the quote
    does not exist or this user may not see it.
    """
    with db.connection() as conn, conn.cursor() as cur:
        quote = _locked_quote(cur, ref, quote_id, user)
        if not quote:
            return False

        if rate is not None:
            new_rate = rate.strip() or None
            if new_rate != (quote["quoted_rate"] or None):
                cur.execute(
                    "INSERT INTO enquiry_rate_history (quote_id, old_rate) VALUES (%s, %s)",
                    (quote_id, quote["quoted_rate"]),
                )
                cur.execute(
                    "UPDATE enquiry_quotes SET quoted_rate = %s, updated_at = now() WHERE id = %s",
                    (new_rate, quote_id),
                )
            if new_rate and quote["status"] == "sent":
                cur.execute(
                    "UPDATE enquiries SET status = 'quoting' WHERE id = %s AND status = 'sent'",
                    (quote["enquiry_id"],),
                )

        if notes is not None:
            cur.execute(
                "UPDATE enquiry_quotes SET notes = %s, updated_at = now() WHERE id = %s",
                (notes.strip() or None, quote_id),
            )
    return True


def mark_winner(ref: str, quote_id: int, user: CurrentUser) -> bool:
    """Set the winning quote and status 'confirmed'. False when the quote is
    not one of this enquiry's, or this user may not see it. Raises
    AlreadyBooked once the enquiry is booked."""
    with db.connection() as conn, conn.cursor() as cur:
        quote = _locked_quote(cur, ref, quote_id, user)
        if not quote:
            return False
        if quote["status"] == "booked":
            raise AlreadyBooked
        cur.execute(
            "UPDATE enquiries SET winner_quote_id = %s, status = 'confirmed' WHERE id = %s",
            (quote_id, quote["enquiry_id"]),
        )
    return True

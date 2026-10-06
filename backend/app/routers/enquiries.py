"""The Enquiries screen (the rate summary): list, one enquiry, edit a quote,
mark the winner.

Enquiries are written by POST /api/enquiry (routers/bookings.py) when the
email goes out. Who sees what is enforced in services/enquiries.py, in SQL —
a normal user their own, an admin all. A ref this user may not see answers
404, exactly like one that does not exist.

Forwarder email addresses are never sent to the browser — names only, the
same as GET /api/forwarders.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.config import settings
from app.deps import CurrentUser, require_auth
from app.services import enquiries

router = APIRouter()

_NOT_FOUND = "That enquiry was not found."


class QuoteUpdateIn(BaseModel):
    """Either or both. Free text — an operator-judgement field, never validated
    beyond a length cap. '' clears it."""

    quoted_rate: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=1000)


class WinnerIn(BaseModel):
    quote_id: int = Field(gt=0)


def _iso(value):
    return value.isoformat() if value else None


def _summary(row: dict) -> dict:
    return {
        "ref": row["ref"],
        # Every enquiry loads at our own port, never the sailing row's.
        "origin": settings.enquiry_origin_port,
        "vessel": row["vessel"] or "",
        "voyage": row["voyage"] or "",
        "carrier": row["carrier"] or "",
        "pod_name": row["pod_name"] or "",
        "country": row["country"] or "",
        "etd": _iso(row["etd"]),
        "created_by": row["created_by"],
        "created_at": _iso(row["created_at"]),
        "status": row["status"],
    }


def _detail(row: dict) -> dict:
    return {
        **_summary(row),
        "eta": _iso(row["eta"]),
        "transit_days": row["transit_days"],
        "stuffing_date": row["stuffing_date"] or "",
        "containers": row["containers"] or "",
        "net_weight": row["net_weight"] or "",
        "gross_weight": row["gross_weight"] or "",
        "commodity": row["commodity"] or "",
        "remarks": row["remarks"] or "",
        "winner_quote_id": row["winner_quote_id"],
        "quotes": [
            {
                "id": q["id"],
                "forwarder_name": q["forwarder_name"],
                "replied": q["replied_at"] is not None,
                "replied_at": _iso(q["replied_at"]),
                "quoted_rate": q["quoted_rate"] or "",
                "notes": q["notes"] or "",
                "updated_at": _iso(q["updated_at"]),
            }
            for q in row["quotes"]
        ],
    }


def _ok(data, message: str = "") -> dict:
    return {"status": "ok", "data": data, "message": message}


def _found(ref: str, user: CurrentUser) -> dict:
    row = enquiries.get(ref, user)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND)
    return _detail(row)


def _with_rates(row: dict) -> dict:
    """A summary plus one cell per forwarder it was sent to — the rate table."""
    return {
        **_summary(row),
        "quotes": [
            {"id": q["id"], "forwarder_name": q["forwarder_name"], "quoted_rate": q["quoted_rate"] or ""}
            for q in row["quotes"]
        ],
    }


@router.get("/enquiries")
def list_enquiries(user: CurrentUser = Depends(require_auth), limit: int = 200) -> dict:
    """This user's enquiries, newest first, each with the forwarders it went to
    and their rates. Admin sees everyone's."""
    return _ok([_with_rates(r) for r in enquiries.list_with_quotes(user, limit)])


@router.get("/enquiries/{ref}")
def get_enquiry(ref: str, user: CurrentUser = Depends(require_auth)) -> dict:
    return _ok(_found(ref, user))


@router.patch("/enquiries/{ref}/quotes/{quote_id}")
def update_quote(
    ref: str, quote_id: int, body: QuoteUpdateIn, user: CurrentUser = Depends(require_auth)
) -> dict:
    """Save a forwarder's rate and/or notes. Answers the whole enquiry, so the
    screen shows the new status and lowest rate without a second call."""
    if not enquiries.update_quote(ref, quote_id, user, rate=body.quoted_rate, notes=body.notes):
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND)
    return _ok(_found(ref, user), "Saved.")


@router.post("/enquiries/{ref}/winner")
def mark_winner(ref: str, body: WinnerIn, user: CurrentUser = Depends(require_auth)) -> dict:
    """Mark one forwarder's quote as the winner; the enquiry becomes 'confirmed'."""
    try:
        done = enquiries.mark_winner(ref, body.quote_id, user)
    except enquiries.AlreadyBooked:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This enquiry is already booked — the winner can't change."
        ) from None
    if not done:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND)
    return _ok(_found(ref, user), "Winner marked.")

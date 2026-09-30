"""The sailing schedule.

Read from the `schedule` table only — never from the Google Sheet directly.
The sheet reaches the table through services/sheet_sync.py.

SCAFFOLD: handlers are stubs. Built on feature/finder.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.deps import CurrentUser, require_auth

router = APIRouter()

MAX_ROWS = 2000  # every schedule query is bounded


def _not_built(name: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=f"{name} is not built yet.",
    )


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
    limit: int = Query(default=MAX_ROWS, le=MAX_ROWS),
):
    """Filtered sailings.

    routing maps to `transshipment`: '0' is Direct, '1'+ is Indirect, blank is
    unlabelled and appears only under 'all'.
    """
    raise _not_built("Schedule")


@router.get("/forwarders")
def get_forwarders(user: CurrentUser = Depends(require_auth)):
    """Names only. The addresses stay server-side and never reach the browser."""
    raise _not_built("Forwarders")

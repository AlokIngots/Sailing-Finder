"""Sailing Finder — FastAPI entry point.

Mounts the API routers and serves the built React app.

SCAFFOLD STATE: routers are mounted but their handlers return 501 until each
feature is built on its own branch. The wiring, the auth gate, the response
envelope and the static serving are real.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import config, db
from app.config import settings
from app.routers import auth, bookings, schedule, share, wa_contacts

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
log = logging.getLogger("sailing_finder")


@asynccontextmanager
async def lifespan(_: FastAPI):
    config.validate(settings)
    db.open_pool()
    log.info("started (%s, %s)", settings.env, settings.timezone)
    yield
    db.close_pool()
    log.info("stopped")


app = FastAPI(
    title="Sailing Finder",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None,
    openapi_url=None if settings.is_production else "/openapi.json",
)


# ---------------------------------------------------------------------------
# Response envelope: every API response is {status, data, message}.
# ---------------------------------------------------------------------------
def envelope(data=None, message: str = "", status_: str = "ok") -> dict:
    return {"status": status_, "data": data, "message": message}


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    if not request.url.path.startswith("/api"):
        raise exc
    return JSONResponse(
        status_code=exc.status_code,
        content=envelope(None, str(exc.detail), "error"),
    )


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    # Say which field is missing, never echo the submitted values back.
    fields = ", ".join(".".join(str(p) for p in e["loc"][1:]) for e in exc.errors())
    return JSONResponse(
        status_code=422,
        content=envelope(None, f"Please check these fields: {fields}", "error"),
    )


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception):
    # Log the real error internally; return a sanitised message to the browser.
    log.exception("[%s %s] %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=500,
        content=envelope(None, "Something went wrong. Please try again.", "error"),
    )


# ---------------------------------------------------------------------------
# Health — reflects real state, so it hits the database rather than just 200.
# ---------------------------------------------------------------------------
@app.get("/healthz", include_in_schema=False)
def healthz():
    try:
        db.fetch_one("SELECT 1 AS ok")
    except Exception as exc:  # noqa: BLE001 - reported, not raised
        log.error("healthz: database unavailable: %s", exc)
        return JSONResponse(
            status_code=503,
            content=envelope({"db": "down"}, "database unavailable", "error"),
        )
    return envelope({"db": "up"})


# ---------------------------------------------------------------------------
# API. Only /api/login and /api/logout are open; the rest depend on require_auth.
# ---------------------------------------------------------------------------
app.include_router(auth.router, prefix="/api", tags=["auth"])
app.include_router(schedule.router, prefix="/api", tags=["schedule"])
app.include_router(bookings.router, prefix="/api", tags=["bookings"])
app.include_router(share.router, prefix="/api", tags=["share"])
app.include_router(wa_contacts.router, prefix="/api", tags=["wa-contacts"])


@app.api_route("/api/{rest:path}", methods=["GET", "POST", "PUT", "DELETE"], include_in_schema=False)
def api_not_found(rest: str):
    """An unknown /api path must never fall through to index.html, or the
    frontend gets HTML where it expected JSON."""
    return JSONResponse(status_code=404, content=envelope(None, "Not found", "error"))


# ---------------------------------------------------------------------------
# Built React app. In the image this is /app/frontend_dist; in a checkout it is
# frontend/dist. Serving it from the backend keeps one origin, so the session
# cookie works without CORS.
# ---------------------------------------------------------------------------
def _dist_dir() -> Path | None:
    for candidate in (
        os.environ.get("FRONTEND_DIST"),
        settings.frontend_dist,
        Path(__file__).resolve().parents[2] / "frontend" / "dist",
    ):
        if candidate and (Path(candidate) / "index.html").exists():
            return Path(candidate)
    return None


dist = _dist_dir()
if dist:
    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        """React Router handles the three views client-side, so any non-API
        path serves index.html. index.html contains no schedule data — it is
        fetched after login."""
        asset = dist / full_path
        if full_path and asset.is_file():
            return FileResponse(asset)
        return FileResponse(dist / "index.html")

else:  # pragma: no cover - only before the first `npm run build`
    log.warning("frontend build not found — run `npm run build` in frontend/")

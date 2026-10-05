"""The SPA catch-all serves files from the frontend build only.

It has no login, so anything it can be talked into reading is public. The
paths below are what the route receives AFTER URL-decoding — '..%2f' arrives
as '../', '..%5c' as '..\\'.
"""

from __future__ import annotations

import pytest

from app import main
from app.main import inside_dist


@pytest.fixture
def layout(tmp_path):
    """dist/ with a build in it, and a secret file next to dist/."""
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html>")
    (dist / "assets" / "app.js").write_text("js")
    (tmp_path / "secret.env").write_text("SMTP_PASS=do-not-serve")
    return dist.resolve(), (tmp_path / "secret.env").resolve()


def test_files_inside_the_build_are_found(layout):
    dist, _ = layout
    assert inside_dist(dist, "index.html") == dist / "index.html"
    assert inside_dist(dist, "assets/app.js") == dist / "assets" / "app.js"
    assert inside_dist(dist, "assets/../index.html") == dist / "index.html"  # stays inside


def test_a_client_side_route_is_inside_and_falls_back_to_index(layout):
    dist, _ = layout
    found = inside_dist(dist, "finder")
    assert found is not None and not found.is_file()  # spa() then serves index.html


@pytest.mark.parametrize(
    "path",
    [
        "../secret.env",
        "assets/../../secret.env",
        "..\\secret.env",
        "./../secret.env",
        "../dist-sibling/x",
        "..",
    ],
)
def test_paths_that_climb_out_of_the_build_are_refused(layout, path):
    dist, _ = layout
    assert inside_dist(dist, path) is None


def test_absolute_paths_are_refused(layout):
    dist, secret = layout
    assert inside_dist(dist, str(secret)) is None


def test_a_nul_byte_neither_crashes_nor_reaches_a_file(layout):
    # Refused where the OS rejects it (Linux); on Windows it resolves inside
    # dist to a name that is not a file, so spa() falls back to index.html.
    dist, _ = layout
    found = inside_dist(dist, "a\x00b")
    assert found is None or (found.is_relative_to(dist) and not found.is_file())


# ---------------------------------------------------------------------------
# Over HTTP, against the real route — only where a frontend build exists.
# ---------------------------------------------------------------------------
needs_build = pytest.mark.skipif(main.dist is None, reason="no frontend build (run npm run build)")


@needs_build
@pytest.mark.parametrize(
    "url",
    [
        "/..%2fpackage.json",
        "/%2e%2e/%2e%2e/README.md",
        "/%2e%2e%2f%2e%2e%2fREADME.md",
        "/..%5c..%5cREADME.md",
    ],
)
def test_encoded_traversal_gets_a_404_over_http(client, url):
    response = client.get(url)
    assert response.status_code == 404
    assert b"sailing-finder" not in response.content.lower()


@needs_build
@pytest.mark.parametrize("url", ["/", "/finder", "/bookings/ABC-1", "/assets/../index.html"])
def test_normal_pages_still_get_the_app(client, url):
    response = client.get(url)
    assert response.status_code == 200
    assert response.content.lstrip().lower().startswith(b"<!doctype html")

"""The finder's filtering and sorting rules.

build_schedule_query turns the finder's state into one parameterised query, so
the rules can be checked here without a database. What is NOT checked here is
whether Postgres agrees — the SQL itself still needs running against a real
server. See the PR notes.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.routers.schedule import MAX_ROWS, build_schedule_query, ship_type, shape
from app.services import ports


def sql_for(**kwargs) -> str:
    return build_schedule_query(**kwargs)[0]


def where_for(**kwargs) -> str:
    """Just the WHERE clause — the column list mentions most names too."""
    return sql_for(**kwargs).split("WHERE", 1)[1].split("ORDER BY", 1)[0]


def params_for(**kwargs) -> list:
    return build_schedule_query(**kwargs)[1]


# ---------------------------------------------------------------------------
# Always true
# ---------------------------------------------------------------------------
def test_departed_sailings_are_never_returned():
    """Cleanup removes them nightly, but a stale row must not slip through."""
    assert "etd >= CURRENT_DATE" in sql_for()


def test_every_query_is_bounded():
    sql, params = build_schedule_query()
    assert "LIMIT %s" in sql
    assert params[-1] == MAX_ROWS


def test_limit_cannot_exceed_the_cap():
    assert params_for(limit=999_999)[-1] == MAX_ROWS


def test_nothing_is_interpolated_into_the_sql():
    """Every user value arrives as a bound parameter."""
    sql, params = build_schedule_query(
        country="Netherlands",
        pod_code="nlrtm",
        carrier="MSC",
        etd_from=date(2026, 10, 1),
    )
    for value in ("Netherlands", "nlrtm", "MSC", "2026-10-01"):
        assert value not in sql
    assert "NL%" in params and "NLRTM" in params and "MSC" in params


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------
def test_no_filters_means_no_extra_clauses():
    assert where_for().strip() == "etd >= CURRENT_DATE"


def test_country_becomes_a_locode_prefix():
    sql, params = build_schedule_query(country="Netherlands")
    assert "upper(pod_code) LIKE %s" in sql
    assert "NL%" in params


def test_unknown_country_matches_nothing():
    """Better an empty list than quietly showing every port on earth."""
    assert "FALSE" in sql_for(country="Atlantis")


def test_port_is_matched_case_insensitively():
    assert "NLRTM" in params_for(pod_code=" nlrtm ")


def test_both_date_ranges_are_applied():
    sql, params = build_schedule_query(
        etd_from=date(2026, 10, 1),
        etd_to=date(2026, 10, 31),
        eta_from=date(2026, 11, 1),
        eta_to=date(2026, 11, 30),
    )
    assert "etd >= %s" in sql and "etd <= %s" in sql
    assert "eta >= %s" in sql and "eta <= %s" in sql
    assert params[:4] == [date(2026, 10, 1), date(2026, 10, 31), date(2026, 11, 1), date(2026, 11, 30)]


def test_a_sailing_with_no_eta_survives_an_arrival_filter():
    """The reference skips the arrival test when a sailing has no ETA, so a
    carrier that published no arrival date is not quietly dropped."""
    where = where_for(eta_from=date(2026, 11, 1))
    assert "eta IS NULL OR eta >= %s" in where


# ---------------------------------------------------------------------------
# Direct / Indirect
# ---------------------------------------------------------------------------
def test_all_routing_filters_nothing():
    """Blank transshipment appears only under All, so All adds no clause."""
    assert "transshipment" not in where_for(routing="all")


def test_direct_selects_zero_transshipments():
    where = where_for(routing="direct")
    assert "::numeric = 0" in where
    assert "substring(btrim(coalesce(transshipment" in where


def test_indirect_selects_a_non_zero_count():
    assert "::numeric <> 0" in where_for(routing="indirect")


@pytest.mark.parametrize(
    "value,expected",
    [
        ("0", "direct"),
        (" 0 ", "direct"),
        ("0.0", "direct"),
        ("1", "indirect"),
        ("2", "indirect"),
        # parseFloat reads a leading number and ignores the rest, so a labelled
        # transshipment port still counts as one leg.
        ("1 (SIN)", "indirect"),
        ("1.5", "indirect"),
        ("", "unlabelled"),
        (None, "unlabelled"),
        ("   ", "unlabelled"),
        ("direct", "unlabelled"),
        ("transshipment", "unlabelled"),
    ],
)
def test_ship_type_matches_the_reference(value, expected):
    """Ported from reference/Index.html's shipType().

    The tag on a row and the filter that selected it must agree, so the SQL and
    this function implement the same parseFloat rule: a leading number decides
    it, and only a value with no leading number at all is unlabelled.
    """
    assert ship_type(value) == expected


# ---------------------------------------------------------------------------
# Next per port, sorting
# ---------------------------------------------------------------------------
def test_all_sailings_is_a_plain_select():
    assert "DISTINCT ON" not in sql_for(mode="all")


def test_next_per_port_takes_one_row_per_port_and_carrier():
    """The reference keys on pod_code|carrier, not the port alone — a customer
    still sees every line that serves the port, just once each."""
    sql = sql_for(mode="next_per_port")
    assert "DISTINCT ON (pod_code, carrier)" in sql
    # The soonest departure per pair, then the user's sort on top.
    assert "ORDER BY pod_code, carrier, etd ASC NULLS LAST" in sql


@pytest.mark.parametrize(
    "sort,first_column",
    [("etd", "etd ASC"), ("transit", "transit_days ASC"), ("eta", "eta ASC")],
)
def test_sort_options(sort, first_column):
    assert sql_for(sort=sort).rsplit("ORDER BY", 1)[1].strip().startswith(first_column)


def test_unknown_sort_falls_back_to_soonest_departure():
    assert sql_for(sort="whatever").rsplit("ORDER BY", 1)[1].strip().startswith("etd ASC")


def test_sailings_without_a_transit_time_sort_last():
    """A blank transit must not jump to the top of "fastest transit"."""
    assert "transit_days ASC NULLS LAST" in sql_for(sort="transit")


# ---------------------------------------------------------------------------
# Country derivation
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "code,country",
    [
        ("NLRTM", "Netherlands"),
        ("INNSA", "India"),
        ("AEJEA", "United Arab Emirates"),
        ("USNYC", "United States"),
        ("", ""),
        (None, ""),
    ],
)
def test_country_comes_from_the_locode_prefix(code, country):
    assert ports.country_for_port(code) == country


def test_country_round_trips():
    assert ports.iso_for_country("Netherlands") == "NL"
    assert ports.iso_for_country("netherlands") == "NL"
    assert ports.iso_for_country("Atlantis") == ""


def test_country_options_are_sorted_and_unique():
    assert ports.country_options(["NLRTM", "NLAMS", "INNSA", "", None]) == [
        "India",
        "Netherlands",
    ]


# ---------------------------------------------------------------------------
# Row shaping
# ---------------------------------------------------------------------------
ROW = {
    "row_key": "MSC|INNSA|NLRTM|MSC ORION|231W|2026-10-05",
    "carrier": "MSC",
    "pol_code": "INNSA",
    "pol_name": "Nhava Sheva",
    "pod_code": "NLRTM",
    "pod_name": "Rotterdam",
    "vessel_name": "MSC ORION",
    "voyage_no": "231W",
    "etd": date(2026, 10, 5),
    "eta": date(2026, 11, 11),
    "transit_days": 37,
    "transshipment": "0",
    "service": "INDAMEX",
}


def test_shape_adds_country_and_ship_type():
    out = shape(ROW)
    assert out["country"] == "Netherlands"
    assert out["ship_type"] == "direct"


def test_shape_sends_dates_as_plain_iso():
    out = shape(ROW)
    assert out["etd"] == "2026-10-05"
    assert out["eta"] == "2026-11-11"


def test_shape_turns_missing_text_into_empty_strings_not_null():
    out = shape({**ROW, "service": None, "voyage_no": None})
    assert out["service"] == ""
    assert out["voyage_no"] == ""


def test_shape_keeps_a_missing_transit_as_null():
    """'—' is a display decision, not a data one."""
    assert shape({**ROW, "transit_days": None})["transit_days"] is None


# ---------------------------------------------------------------------------
# The endpoint
# ---------------------------------------------------------------------------
def test_schedule_needs_a_session(client):
    assert client.get("/api/schedule").status_code == 401


def test_filters_endpoint_needs_a_session(client):
    assert client.get("/api/schedule/filters").status_code == 401


def test_schedule_returns_shaped_rows(client, fake_db):
    from app.services import security

    fake_db.add_user("alok", security.hash_password("correct-horse-battery"))
    client.post("/api/login", json={"username": "alok", "password": "correct-horse-battery"})

    fake_db.rows = [dict(ROW)]
    body = client.get("/api/schedule").json()

    assert body["status"] == "ok"
    assert body["data"]["count"] == 1
    assert body["data"]["truncated"] is False
    assert body["data"]["rows"][0]["country"] == "Netherlands"

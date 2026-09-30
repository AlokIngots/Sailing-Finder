"""Reading the scrapers' sheet.

The Google call itself is not exercised — there is no service-account key
outside the VPS. What is covered is everything that happens to the values once
they arrive, which is where the sheet's untidiness actually bites.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest

from app.services import sheet_sync

HEADER = [
    "Carrier", "POL Code", "POL Name", "POD Code", "POD Name", "Vessel",
    "Voyage", "ETD", "ETA", "Transit Days", "Transshipment", "Service",
    "Source", "Pulled On", "Row Key",
]

ROW = [
    "MSC", "INNSA", "Nhava Sheva", "NLRTM", "Rotterdam", "MSC ORION",
    "231W", "2026-10-05", "2026-11-11", "37", "0", "INDAMEX",
    "msc-scraper", "2026-09-30", "msc-231w-nlrtm",
]


# ---------------------------------------------------------------------------
# Headers
# ---------------------------------------------------------------------------
def test_headers_are_matched_by_name():
    mapping = sheet_sync.map_headers(HEADER)
    assert mapping["carrier"] == 0
    assert mapping["etd"] == 7
    assert mapping["row_key"] == 14


def test_header_matching_ignores_case_spacing_and_punctuation():
    mapping = sheet_sync.map_headers(["  CARRIER ", "P.O.L. Code", "Transit (days)"])
    assert mapping["carrier"] == 0
    assert mapping["pol_code"] == 1
    assert mapping["transit_days"] == 2


def test_known_alternative_spellings_are_understood():
    """Different scrapers label the same column differently."""
    mapping = sheet_sync.map_headers(["Line", "Departs", "Arrives", "Transhipment"])
    assert mapping["carrier"] == 0
    assert mapping["etd"] == 1
    assert mapping["eta"] == 2
    assert mapping["transshipment"] == 3


def test_a_column_inserted_in_the_middle_does_not_shift_everything():
    """Matching by name is the whole point: positions move, names do not."""
    header = ["Carrier", "Surprise New Column", "ETD"]
    assert sheet_sync.map_headers(header)["etd"] == 2


# ---------------------------------------------------------------------------
# Dates
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "text",
    ["2026-10-05", "05 Oct 2026", "5 October 2026", "05-Oct-2026", "05/10/2026", "05.10.2026"],
)
def test_the_date_shapes_the_scrapers_produce(text):
    assert sheet_sync.parse_date(text) == date(2026, 10, 5)


def test_ambiguous_dates_are_read_day_first():
    """05/06/2026 is 5 June here, the way the team writes it — not 6 May."""
    assert sheet_sync.parse_date("05/06/2026") == date(2026, 6, 5)


@pytest.mark.parametrize("value", ["", None, "   ", "next Tuesday", "TBA"])
def test_unusable_dates_become_none_rather_than_an_error(value):
    assert sheet_sync.parse_date(value) is None


def test_real_dates_pass_straight_through():
    assert sheet_sync.parse_date(date(2026, 10, 5)) == date(2026, 10, 5)
    assert sheet_sync.parse_date(datetime(2026, 10, 5, 13, 30)) == date(2026, 10, 5)


@pytest.mark.parametrize(
    "value,expected",
    [("37", 37), (" 37 days ", 37), ("", None), (None, None), ("n/a", None), ("~42", 42)],
)
def test_transit_days_survives_units_and_noise(value, expected):
    assert sheet_sync.parse_int(value) == expected


# ---------------------------------------------------------------------------
# Rows
# ---------------------------------------------------------------------------
def test_a_clean_sheet_parses():
    rows = sheet_sync.parse_rows([HEADER, ROW])
    assert len(rows) == 1

    row = rows[0]
    assert row["carrier"] == "MSC"
    assert row["etd"] == date(2026, 10, 5)
    assert row["eta"] == date(2026, 11, 11)
    assert row["transit_days"] == 37
    assert row["row_key"] == "msc-231w-nlrtm"


def test_rows_without_a_departure_date_are_dropped():
    """No ETD means it cannot be filtered, sorted, or cleaned up."""
    no_etd = list(ROW)
    no_etd[7] = ""
    assert sheet_sync.parse_rows([HEADER, ROW, no_etd]) == sheet_sync.parse_rows([HEADER, ROW])


def test_a_missing_row_key_is_generated_from_the_sailing():
    no_key = list(ROW)
    no_key[14] = ""
    row = sheet_sync.parse_rows([HEADER, no_key])[0]
    assert row["row_key"] == "MSC|INNSA|NLRTM|MSC ORION|231W|2026-10-05"


def test_the_generated_key_is_stable_across_reads():
    no_key = list(ROW)
    no_key[14] = ""
    first = sheet_sync.parse_rows([HEADER, no_key])[0]["row_key"]
    second = sheet_sync.parse_rows([HEADER, no_key])[0]["row_key"]
    assert first == second, "an unstable key would duplicate the sailing every sync"


def test_short_rows_do_not_blow_up():
    """Sheets ragged-right: trailing empty cells simply are not there."""
    row = sheet_sync.parse_rows([HEADER, ROW[:9]])[0]
    assert row["transit_days"] is None
    assert row["service"] == ""


def test_an_unrecognisable_header_falls_back_to_column_order():
    values = [["a", "b", "c"], ROW]
    rows = sheet_sync.parse_rows(values)
    # Both lines are treated as data, but only the one with a real ETD survives.
    assert len(rows) == 1
    assert rows[0]["carrier"] == "MSC"


def test_an_empty_sheet_parses_to_nothing():
    assert sheet_sync.parse_rows([]) == []


# ---------------------------------------------------------------------------
# Upsert
# ---------------------------------------------------------------------------
def test_the_upsert_updates_rather_than_duplicates():
    """ON CONFLICT (row_key) DO UPDATE is what stops a re-sync doubling the table."""
    assert "ON CONFLICT (row_key) DO UPDATE" in sheet_sync.UPSERT
    assert "DELETE" not in sheet_sync.UPSERT.upper()
    assert "TRUNCATE" not in sheet_sync.UPSERT.upper()


def test_the_upsert_refreshes_every_column_except_the_key():
    for column in sheet_sync.COLUMNS:
        if column == "row_key":
            continue
        assert f"{column}" in sheet_sync.UPSERT


def test_nothing_is_written_for_an_empty_batch():
    assert sheet_sync.upsert_rows([]) == 0


def test_an_empty_read_is_an_error_not_a_quiet_no_op(monkeypatch):
    """A permissions or tab-name problem must be loud, or a stale schedule
    goes unnoticed for a week."""
    monkeypatch.setattr(sheet_sync, "read_sheet", lambda: [])
    with pytest.raises(sheet_sync.SheetSyncError):
        sheet_sync.sync_schedule_from_sheet()


def test_a_sheet_of_unusable_rows_is_an_error_too(monkeypatch):
    monkeypatch.setattr(sheet_sync, "read_sheet", lambda: [HEADER])
    with pytest.raises(sheet_sync.SheetSyncError):
        sheet_sync.sync_schedule_from_sheet()

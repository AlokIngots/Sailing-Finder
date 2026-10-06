"""Enquiry: the forwarder list, the email a forwarder receives, the send, and
the rate summary (GET /api/enquiries).

Nothing here touches a real SMTP server: mailer._deliver is replaced, and the
built messages it was handed are checked — sender, To, CC and body. Nor a real
database: the enquiry number and the save (services/enquiries) are replaced
too, and what they were handed is checked.
"""

from __future__ import annotations

from datetime import date

import pytest

from app import config
from app.config import Forwarder
from app.routers.bookings import EnquiryIn
from app.routers.schedule import shape
from app.services import enquiries, enquiry_email, mailer, security

GOOD_PASSWORD = "correct-horse-battery"

#: The real one, before the autouse `saved` fixture replaces it.
REAL_NEXT_REF = enquiries.next_ref

FORWARDERS = (
    Forwarder("f1", "Express Cargo", "to1@fwd-one.example", ("cc1a@fwd-one.example", "cc1b@fwd-one.example")),
    Forwarder("f2", "Vishal", "to2@fwd-two.example", ("cc2a@fwd-two.example",)),
    Forwarder("f3", "ISA", "to3@fwd-three.example", ()),
    Forwarder("f4", "Shree", "to4@fwd-four.example", ("cc4a@fwd-four.example",)),
)

ROW = {
    "row_key": "a",
    "pol_code": "INNSA",
    "pol_name": "Nhava Sheva",
    "carrier": "MSC",
    "pod_code": "ITGOA",
    "pod_name": "Genoa",
    "vessel_name": "MSC AURORA (270E)",
    "voyage_no": "",
    "etd": date(2026, 10, 5),
    "eta": date(2026, 11, 1),
    "transit_days": 27,
    "transshipment": "0",
    "service": "",
}

FORM = {
    "row_key": "a",
    "stuffing": "2026-10-02",
    "container": "2 x 20 ft",
    "net_wt": "42,000 kg",
    "gross_wt": "44,500 kg",
    "commodity": "Stainless steel bright bars",
    "remarks": "Target USD 900",
    "forwarder_ids": ["f1", "f2", "f3", "f4"],
}


@pytest.fixture
def use_settings(monkeypatch):
    """Swap settings fields for one test, in every module that reads them."""
    import dataclasses

    from app.routers import bookings as bookings_router, schedule as schedule_router

    def apply(**changes):
        current = dataclasses.replace(mailer.settings, **changes)
        for module in (mailer, enquiry_email, bookings_router, schedule_router):
            monkeypatch.setattr(module, "settings", current)
        return current

    return apply


@pytest.fixture
def ready(use_settings):
    """Four forwarders and a configured lk.exports mailbox."""
    return use_settings(
        forwarders=FORWARDERS,
        enquiry_smtp_host="smtp.example",
        enquiry_smtp_user="",
        enquiry_smtp_pass="real-secret",
        enquiry_mail_from="lk.exports@alokindia.com",
    )


@pytest.fixture
def signed_in(client, fake_db):
    fake_db.add_user("priya", security.hash_password(GOOD_PASSWORD), name="Priya", role="user")
    assert client.post("/api/login", json={"username": "priya", "password": GOOD_PASSWORD}).status_code == 200
    fake_db.rows = [dict(ROW)]
    return client


@pytest.fixture(autouse=True)
def saved(monkeypatch):
    """Number enquiries ENQ-0001, ENQ-0002, ... and record what would be saved
    as (ref, forwarder names, username), instead of using the database."""
    calls = []
    counter = iter(range(1, 10_000))
    monkeypatch.setattr(enquiries, "next_ref", lambda: f"ENQ-{next(counter):04d}")

    def fake_record(ref, sailing, fields, username, forwarders):
        calls.append((ref, [f.name for f in forwarders], username))

    monkeypatch.setattr(enquiries, "record", fake_record)
    return calls


@pytest.fixture
def delivered(monkeypatch):
    """Record (account, message) instead of talking to SMTP."""
    sent = []

    async def fake_deliver(account, msg):
        sent.append((account, msg))

    monkeypatch.setattr(mailer, "_deliver", fake_deliver)
    return sent


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
@pytest.fixture
def forwarder_env(monkeypatch):
    """Start from no FORWARDER_* at all (conftest and a local .env set some),
    then set forwarders n -> (name, to, cc)."""
    import os

    for key in [k for k in os.environ if k.startswith("FORWARDER_")]:
        monkeypatch.delenv(key)

    def apply(**by_number):
        for n, (name, email, cc) in by_number.items():
            number = n.lstrip("n")
            if name:
                monkeypatch.setenv(f"FORWARDER_{number}_NAME", name)
            if email:
                monkeypatch.setenv(f"FORWARDER_{number}_EMAIL", email)
            if cc:
                monkeypatch.setenv(f"FORWARDER_{number}_CC", cc)

    return apply


def test_forwarders_are_read_with_to_and_cc(forwarder_env):
    forwarder_env(
        n1=("Express Cargo", "to1@fwd-one.example", " cc1a@fwd-one.example; cc1b@fwd-one.example, to1@fwd-one.example ,"),
        n2=("Shree", "to2@fwd-two.example", ""),
    )

    found = config._forwarders()

    assert [f.id for f in found] == ["f1", "f2"]
    assert found[0].cc == ("cc1a@fwd-one.example", "cc1b@fwd-one.example")  # To is not repeated in CC
    assert found[1].cc == ()


def test_any_number_of_forwarders_is_read_no_code_change(forwarder_env):
    forwarder_env(**{f"n{n}": (f"Forwarder {n}", f"to{n}@fwd.example", "") for n in range(1, 13)})
    found = config._forwarders()
    assert [f.id for f in found] == [f"f{n}" for n in range(1, 13)]
    assert found[-1].name == "Forwarder 12"


def test_reading_stops_at_the_first_missing_number_and_says_so(forwarder_env, caplog):
    forwarder_env(
        n1=("One", "to1@fwd.example", ""),
        n2=("Two", "to2@fwd.example", ""),
        n4=("Four", "to4@fwd.example", ""),
    )
    assert [f.id for f in config._forwarders()] == ["f1", "f2"]

    import dataclasses

    with caplog.at_level("WARNING", logger="app.config"):
        config.validate(dataclasses.replace(config.settings, forwarders=config._forwarders()))
    assert "FORWARDER_4" in caplog.text


def test_a_forwarder_with_a_name_but_no_address_stops_startup(forwarder_env):
    forwarder_env(n1=("One", "to1@fwd.example", ""), n2=("Half set", "", ""))
    with pytest.raises(config.ConfigError, match="FORWARDER_2"):
        config.validate(config.settings)


def test_at_least_one_forwarder_is_required(use_settings):
    with pytest.raises(config.ConfigError, match="at least one forwarder"):
        config.validate(use_settings(forwarders=()))


def test_forwarders_endpoint_gives_names_only(signed_in, ready):
    response = signed_in.get("/api/forwarders")
    assert response.status_code == 200
    assert response.json()["data"] == [{"id": f.id, "name": f.name} for f in FORWARDERS]
    assert "@" not in response.text


def test_forwarders_endpoint_needs_a_session(client):
    assert client.get("/api/forwarders").status_code == 401


# ---------------------------------------------------------------------------
# The email
# ---------------------------------------------------------------------------
def test_the_body_carries_every_form_field_and_the_sailing():
    subject, body = enquiry_email.build(shape(ROW), EnquiryIn(**FORM), "ENQ-0001")

    assert subject == "Rate Enquiry ENQ-0001 — Nhava Sheva to Genoa, Italy"
    lines = body.splitlines()
    for expected in (
        "Carrier: MSC",
        "Vessel / voyage: MSC AURORA / 270E",
        "From: Nhava Sheva (INNSA)",
        "To: Genoa, Italy (ITGOA)",
        "ETD: 5 Oct 2026   ETA: 1 Nov 2026   Transit: 27 days",
        "Stuffing date: 2026-10-02",
        "Containers: 2 x 20 ft",
        "Commodity: Stainless steel bright bars",
        "Weight: 42,000 kg net / 44,500 kg gross",
        "Remarks: Target USD 900",
    ):
        assert expected in lines


def test_the_loading_port_is_always_the_configured_one_never_the_row():
    row = dict(ROW, pol_code="INMUN", pol_name="Mundra")
    subject, body = enquiry_email.build(shape(row), EnquiryIn(**FORM), "ENQ-0001")
    assert subject == "Rate Enquiry ENQ-0001 — Nhava Sheva to Genoa, Italy"
    assert "From: Nhava Sheva (INNSA)" in body.splitlines()
    assert "To: Genoa, Italy (ITGOA)" in body.splitlines()  # destination untouched
    assert "Mundra" not in body and "INMUN" not in body


def test_changing_the_config_changes_the_email_and_the_modal_together(signed_in, ready, use_settings):
    use_settings(enquiry_origin_port="Mundra", enquiry_origin_code="INMUN")
    subject, body = enquiry_email.build(shape(ROW), EnquiryIn(**FORM), "ENQ-0001")
    assert subject.startswith("Rate Enquiry ENQ-0001 — Mundra to")
    assert "From: Mundra (INMUN)" in body.splitlines()

    response = signed_in.get("/api/enquiry-origin")
    assert response.status_code == 200
    assert response.json()["data"] == {"port": "Mundra", "code": "INMUN", "label": "Mundra (INMUN)"}


def test_enquiry_origin_needs_a_session(client):
    assert client.get("/api/enquiry-origin").status_code == 401


def test_empty_optional_fields_are_left_out():
    _, body = enquiry_email.build(shape(dict(ROW, transit_days=None)), EnquiryIn(row_key="a", commodity="", forwarder_ids=["f1"]), "ENQ-0001")
    assert "ETD: 5 Oct 2026   ETA: 1 Nov 2026" in body.splitlines()
    for label in ("Transit:", "Stuffing date:", "Containers:", "Commodity:", "Weight:", "Remarks:"):
        assert label not in body


# ---------------------------------------------------------------------------
# The send
# ---------------------------------------------------------------------------
def test_one_message_per_forwarder_to_its_address_cc_its_colleagues(signed_in, ready, delivered):
    response = signed_in.post("/api/enquiry", json=FORM)

    assert response.status_code == 200, response.text
    assert response.json()["data"] == {"ref": "ENQ-0001", "sent": [f.name for f in FORWARDERS], "failed": [], "saved": True}
    assert len(delivered) == len(FORWARDERS)

    by_to = {msg["To"]: (account, msg) for account, msg in delivered}
    bodies = set()
    for forwarder in FORWARDERS:
        account, msg = by_to[forwarder.email]
        assert "lk.exports@alokindia.com" in msg["From"]
        assert account.user == "lk.exports@alokindia.com"  # sign-in defaults to the From address
        assert (msg["Cc"] or "") == ", ".join(forwarder.cc)
        assert msg["Bcc"] is None
        # No other forwarder's address appears anywhere on this copy.
        others = [a for f in FORWARDERS if f is not forwarder for a in (f.email, *f.cc)]
        assert not any(a in msg.as_string() for a in others)
        bodies.add(msg.get_content())
    assert len(bodies) == 1


def test_only_the_ticked_forwarders_are_emailed(signed_in, ready, delivered):
    response = signed_in.post("/api/enquiry", json=dict(FORM, forwarder_ids=["f4", "f2", "f2"]))

    assert response.status_code == 200, response.text
    assert response.json()["data"] == {"ref": "ENQ-0001", "sent": ["Vishal", "Shree"], "failed": [], "saved": True}
    assert sorted(msg["To"] for _, msg in delivered) == ["to2@fwd-two.example", "to4@fwd-four.example"]


def test_ticking_no_forwarder_is_refused(signed_in, ready, delivered):
    response = signed_in.post("/api/enquiry", json=dict(FORM, forwarder_ids=[]))
    assert response.status_code == 422
    assert "forwarder_ids" in response.json()["message"]
    assert delivered == []


def test_an_unknown_forwarder_sends_nothing(signed_in, ready, delivered):
    response = signed_in.post("/api/enquiry", json=dict(FORM, forwarder_ids=["f1", "f9"]))
    assert response.status_code == 422
    assert delivered == []


def test_share_emails_still_go_from_exports(ready):
    msg = mailer.build_message("buyer@example.com", "Subj", "Body")
    assert "exports@alokindia.com" in msg["From"] and "lk.exports" not in msg["From"]


def test_one_failed_forwarder_does_not_stop_the_others(signed_in, ready, monkeypatch, saved):
    async def flaky(account, msg):
        if msg["To"] == "to2@fwd-two.example":
            raise mailer.MailSendFailed("The mail server refused the address to2@fwd-two.example.")

    monkeypatch.setattr(mailer, "_deliver", flaky)
    response = signed_in.post("/api/enquiry", json=FORM)

    assert response.status_code == 200
    assert response.json()["data"] == {"ref": "ENQ-0001", "sent": ["Express Cargo", "ISA", "Shree"], "failed": ["Vishal"], "saved": True}
    assert "not sent to Vishal" in response.json()["message"]
    # Saved with only the forwarders that actually received it.
    assert saved == [("ENQ-0001", ["Express Cargo", "ISA", "Shree"], "priya")]


def test_when_every_send_fails_the_operator_is_told(signed_in, ready, monkeypatch, saved):
    async def down(account, msg):
        raise mailer.MailSendFailed("Could not reach the mail server. Please try again.")

    monkeypatch.setattr(mailer, "_deliver", down)
    response = signed_in.post("/api/enquiry", json=FORM)
    assert response.status_code == 502
    assert response.json()["message"] == "Could not reach the mail server. Please try again."
    assert saved == []  # nothing went out, so nothing is saved


def test_without_the_lk_exports_password_it_says_so(signed_in, ready, use_settings, delivered):
    use_settings(enquiry_smtp_pass="")
    response = signed_in.post("/api/enquiry", json=FORM)
    assert response.status_code == 503
    assert "ENQUIRY_SMTP" in response.json()["message"]
    assert delivered == []


def test_a_sailing_that_has_gone_is_refused(signed_in, ready, delivered):
    response = signed_in.post("/api/enquiry", json=dict(FORM, row_key="gone"))
    assert response.status_code == 404
    assert delivered == []


def test_enquiry_needs_a_session(client):
    assert client.post("/api/enquiry", json=FORM).status_code == 401


# ---------------------------------------------------------------------------
# The enquiry number
# ---------------------------------------------------------------------------
def test_every_email_carries_the_enquiry_number_and_it_is_saved(signed_in, ready, delivered, saved):
    response = signed_in.post("/api/enquiry", json=FORM)

    assert response.status_code == 200, response.text
    assert response.json()["message"].startswith("ENQ-0001 sent to")
    assert {msg["Subject"] for _, msg in delivered} == {"Rate Enquiry ENQ-0001 — Nhava Sheva to Genoa, Italy"}
    assert saved == [("ENQ-0001", [f.name for f in FORWARDERS], "priya")]


def test_each_enquiry_gets_the_next_number(signed_in, ready, delivered, saved):
    signed_in.post("/api/enquiry", json=FORM)
    second = signed_in.post("/api/enquiry", json=dict(FORM, forwarder_ids=["f3"]))
    assert second.json()["data"]["ref"] == "ENQ-0002"
    assert [ref for ref, _, _ in saved] == ["ENQ-0001", "ENQ-0002"]


def test_a_failed_save_after_sending_still_answers_ok_with_the_number(signed_in, ready, delivered, monkeypatch):
    def broken(*args):
        raise RuntimeError("database down")

    monkeypatch.setattr(enquiries, "record", broken)
    response = signed_in.post("/api/enquiry", json=FORM)

    # The emails went; an error here would make the operator send them again.
    assert response.status_code == 200
    assert response.json()["data"]["ref"] == "ENQ-0001"
    assert response.json()["data"]["saved"] is False
    assert "could not be saved" in response.json()["message"]
    assert "ENQ-0001" in response.json()["message"]


def test_next_ref_is_zero_padded_from_the_sequence(monkeypatch):
    from app import db

    monkeypatch.setattr(db, "fetch_one", lambda sql, params=(): {"n": 7} if "enquiry_ref_seq" in sql else None)
    assert REAL_NEXT_REF() == "ENQ-0007"


# ---------------------------------------------------------------------------
# The rate summary
# ---------------------------------------------------------------------------
LISTED = {
    "id": 1,
    "ref": "ENQ-0001",
    "vessel": "MSC AURORA",
    "voyage": "270E",
    "carrier": "MSC",
    "pod_name": "Genoa",
    "country": "Italy",
    "etd": date(2026, 10, 5),
    "eta": date(2026, 11, 1),
    "transit_days": 27,
    "stuffing_date": "",
    "containers": "",
    "net_weight": "",
    "gross_weight": "",
    "commodity": "",
    "remarks": "",
    "created_by": "priya",
    "created_at": None,
    "status": "sent",
    "winner_quote_id": None,
    "quotes": [
        {"id": 11, "enquiry_id": 1, "forwarder_name": "Express Cargo", "quoted_rate": "USD 1450 all-in"},
        {"id": 12, "enquiry_id": 1, "forwarder_name": "ISA", "quoted_rate": None},
    ],
}


def test_the_rate_summary_lists_enquiries_with_a_rate_per_forwarder(signed_in, monkeypatch):
    asked = []

    def fake_list(user, limit):
        asked.append(user.username)
        return [dict(LISTED)]

    monkeypatch.setattr(enquiries, "list_with_quotes", fake_list)
    response = signed_in.get("/api/enquiries")

    assert response.status_code == 200, response.text
    [row] = response.json()["data"]
    assert asked == ["priya"]  # scoped to the signed-in user in the service
    assert row["ref"] == "ENQ-0001"
    assert row["origin"] == "Nhava Sheva"
    assert row["pod_name"] == "Genoa"
    assert row["quotes"] == [
        {"id": 11, "forwarder_name": "Express Cargo", "quoted_rate": "USD 1450 all-in"},
        {"id": 12, "forwarder_name": "ISA", "quoted_rate": ""},
    ]
    assert "@" not in response.text


def test_a_rate_is_saved_as_free_text(signed_in, monkeypatch):
    calls = []

    def fake_update(ref, quote_id, user, *, rate=None, notes=None):
        calls.append((ref, quote_id, user.username, rate))
        return True

    monkeypatch.setattr(enquiries, "update_quote", fake_update)
    monkeypatch.setattr(enquiries, "get", lambda ref, user: {**LISTED, "quotes": []})
    response = signed_in.patch("/api/enquiries/ENQ-0001/quotes/11", json={"quoted_rate": "about 1400, maybe less"})

    assert response.status_code == 200, response.text
    assert calls == [("ENQ-0001", 11, "priya", "about 1400, maybe less")]


def test_a_quote_this_user_may_not_see_is_not_found(signed_in, monkeypatch):
    monkeypatch.setattr(enquiries, "update_quote", lambda *a, **k: False)
    response = signed_in.patch("/api/enquiries/ENQ-0009/quotes/99", json={"quoted_rate": "x"})
    assert response.status_code == 404


def test_the_rate_summary_needs_a_session(client):
    assert client.get("/api/enquiries").status_code == 401

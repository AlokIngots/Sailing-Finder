"""Email these / WhatsApp: the PDF, the wording, and both sends.

The PDF tests build it uncompressed so the page streams can be searched for
the text that was drawn. Nothing here touches a real SMTP server or Interakt:
the send functions are replaced, and what they were asked to send is checked.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest

from app.config import settings
from app.routers.schedule import shape
from app.services import mailer, pdf, security, share_text, shared_pdfs, whatsapp

GOOD_PASSWORD = "correct-horse-battery"

ROWS = [
    {
        "row_key": "a",
        "pol_code": "INNSA",
        "pol_name": "Nhava Sheva",
        "carrier": "MSC",
        "pod_code": "ITGOA",
        "pod_name": "Genoa",
        "country": "Italy",
        "vessel_name": "MSC AURORA (270E)",
        "voyage_no": "",
        "etd": date(2026, 10, 5),
        "eta": date(2026, 11, 1),
        "transit_days": 27,
        "transshipment": "0",
        "service": "",
    },
    {
        "row_key": "b",
        "pol_code": "INNSA",
        "pol_name": "Nhava Sheva",
        "carrier": "HAPAG-LLOYD",
        "pod_code": "NLRTM",
        "pod_name": "Rotterdam",
        "country": "Netherlands",
        "vessel_name": "BLUE LYRA",
        "voyage_no": "172S",
        "etd": date(2026, 10, 8),
        "eta": date(2026, 11, 19),
        "transit_days": None,
        "transshipment": "2",
        "service": "",
    },
]



@pytest.fixture
def use_settings(monkeypatch):
    """Swap settings fields for one test. Settings is a frozen dataclass, so a
    replaced copy is patched into every module that reads it."""
    import dataclasses

    from app.routers import share as share_router
    from app.services import mailer as m, share_text as t, shared_pdfs as sp, whatsapp as w

    def apply(**changes):
        current = dataclasses.replace(m.settings, **changes)
        for module in (m, t, sp, w):
            monkeypatch.setattr(module, "settings", current)
        return current

    return apply


def shaped():
    return [shape(r) for r in ROWS]


def stream_text(data: bytes) -> str:
    return data.decode("latin-1")


# ---------------------------------------------------------------------------
# The PDF
# ---------------------------------------------------------------------------
def test_pdf_is_a_pdf_with_the_title_and_footer():
    data = pdf.build_schedule_pdf(shaped(), {"line": "Sailing schedule — Nhava Sheva to Italy · 2 sailings", "generated": "03-Oct-2026 15:30"}, compress=False)
    assert data.startswith(b"%PDF-")
    assert data.rstrip().endswith(b"%%EOF")
    text = stream_text(data)
    # The em dash is drawn as a WinAnsi byte, so match the words either side.
    assert "(Alok Ingots " in text and "Sailing Schedule)" in text
    assert "Generated 03-Oct-2026 15:30" in text
    assert "please confirm cut-offs before booking." in text


def test_pdf_has_exactly_the_eight_columns_in_order():
    text = stream_text(pdf.build_schedule_pdf(shaped(), compress=False))
    headings = ["Carrier", "Vessel", "Voyage", "Destination", "ETD", "ETA", "Transit \\(days\\)", "Type"]
    positions = [text.find(f"({h})") for h in headings]
    assert all(p >= 0 for p in positions), dict(zip(headings, positions))
    assert positions == sorted(positions)
    # Columns the brief leaves out must not appear as headings.
    for absent in ("(Service)", "(POL)", "(Routing)", "(Country)"):
        assert absent not in text


def test_pdf_rows_carry_the_cleaned_values():
    assert pdf.table_rows(shaped()) == [
        ["MSC", "MSC AURORA", "270E", "Genoa, Italy", "5 Oct 2026", "1 Nov 2026", "27", "Direct"],
        ["HAPAG-LLOYD", "BLUE LYRA", "172S", "Rotterdam, Netherlands", "8 Oct 2026", "19 Nov 2026", "", "Indirect"],
    ]
    text = stream_text(pdf.build_schedule_pdf(shaped(), compress=False))
    for value in ("MSC AURORA", "270E", "Genoa, Italy", "5 Oct 2026", "Rotterdam, Netherlands", "Direct", "Indirect"):
        assert f"({value})" in text, value
    assert "(MSC AURORA \\(270E\\))" not in text  # bracketed voyage is stripped


def test_unlabelled_sailing_gets_an_empty_type_not_a_guess():
    row = dict(ROWS[0], transshipment="")
    assert pdf.table_rows([shape(row)])[0][7] == ""


def test_pdf_escapes_markup_in_values():
    row = dict(ROWS[0], vessel_name="A & B <X>")
    text = stream_text(pdf.build_schedule_pdf([shape(row)], compress=False))
    # Drawn literally (reportlab splits it into runs), never as entities.
    assert "(A & B <) Tj (X) Tj (>) Tj" in text
    assert "&amp;" not in text and "&lt;" not in text


def test_a_long_list_runs_onto_more_pages_with_the_header_repeated():
    many = shaped() * 60
    text = stream_text(pdf.build_schedule_pdf(many, compress=False))
    assert text.count("(Destination)") >= 3
    assert "Page 3" in text


def test_an_empty_list_still_draws_a_page():
    data = pdf.build_schedule_pdf([], compress=False)
    assert "No sailings match these filters." in stream_text(data)


# ---------------------------------------------------------------------------
# Wording (ported from the reference)
# ---------------------------------------------------------------------------
def test_wording_matches_the_reference():
    rows = shaped()
    assert share_text.email_subject("Italy") == "Sailing schedule — Nhava Sheva to Italy"
    assert share_text.summary_line("Italy", 1) == "Sailing schedule — Nhava Sheva to Italy · 1 sailing"
    body = share_text.email_body("Italy", rows, today=date(2026, 10, 3))
    assert body.startswith("Sailing schedule from Nhava Sheva to Italy\n2 sailing(s), as of 3 Oct 2026\n\n")
    assert "• MSC AURORA (270E) — MSC — to Genoa, Italy — Departs 5 Oct 2026, Arrives 1 Nov 2026 (27 days)" in body
    assert body.endswith("Carrier estimates — please confirm cut-offs before booking.\n\nExport Team")
    assert share_text.whatsapp_body_values("Italy", 2, today=date(2026, 10, 3)) == ["Italy", "3 Oct 2026", "2"]
    assert share_text.pdf_filename(datetime(2026, 10, 3, 9, 5)) == "Sailing_Schedule_03102026_0905.pdf"
    assert share_text.generated_stamp(datetime(2026, 10, 3, 9, 5)) == "03-Oct-2026 09:05"


def test_where_label_follows_port_then_country_then_default():
    from app.routers.share import Filters

    rows = shaped()
    assert share_text.where_label(Filters(pod_code="nlrtm"), rows) == "Rotterdam, Netherlands"
    assert share_text.where_label(Filters(country="Italy"), rows) == "Italy"
    assert share_text.where_label(Filters(), rows) == "Europe & Mediterranean"


def test_numbers_normalise_like_code_gs():
    assert whatsapp.normalise_number("98672 00083") == "919867200083"
    assert whatsapp.normalise_number("+91 98672-00083") == "919867200083"
    assert whatsapp.normalise_number("+44 7700 900123") == "447700900123"
    assert whatsapp.normalise_number("abc") == ""


def test_interakt_payload_matches_code_gs():
    payload = whatsapp.build_payload("919867200083", "https://x/shared/t.pdf", "Sailing_Schedule_1.pdf", ["Italy", "3 Oct 2026", "2"])
    assert payload == {
        "countryCode": "+91",
        "phoneNumber": "9867200083",
        "type": "Template",
        "template": {
            "name": "sailing_schedule",
            "languageCode": "en",
            "headerValues": ["https://x/shared/t.pdf"],
            "fileName": "Sailing_Schedule_1.pdf",
            "bodyValues": ["Italy", "3 Oct 2026", "2"],
        },
    }


def test_the_email_is_from_exports_with_the_pdf_attached():
    msg = mailer.build_message("buyer@example.com", "Subj", "Body", [("S.pdf", b"%PDF-1.4 x", "application/pdf")])
    assert "exports@alokindia.com" in msg["From"]
    assert msg["To"] == "buyer@example.com"
    parts = list(msg.iter_attachments())
    assert [(p.get_filename(), p.get_content_type()) for p in parts] == [("S.pdf", "application/pdf")]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@pytest.fixture
def signed_in(client, fake_db):
    fake_db.add_user("priya", security.hash_password(GOOD_PASSWORD), name="Priya", role="user")
    assert client.post("/api/login", json={"username": "priya", "password": GOOD_PASSWORD}).status_code == 200
    fake_db.rows = list(ROWS)
    return client


def test_preview_pdf_needs_a_session(client):
    assert client.get("/api/share/pdf").status_code == 401


def test_preview_pdf_works_without_any_keys(signed_in, monkeypatch, use_settings):
    use_settings(smtp_pass="")
    use_settings(interakt_api_key="")
    response = signed_in.get("/api/share/pdf", params={"country": "Italy", "etd_from": "", "routing": "all"})
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"].startswith('inline; filename="Sailing_Schedule_')
    assert response.content.startswith(b"%PDF-")


def test_preview_rejects_a_bad_date(signed_in):
    assert signed_in.get("/api/share/pdf", params={"etd_from": "not-a-date"}).status_code == 422


EMAIL = {"to": ["buyer@example.com"], "filters": {"country": "Italy", "etd_from": ""}}
WA = {"number": "98672 00083", "save": True, "name": "Buyer", "filters": {"country": "Italy"}}


def test_email_without_smtp_settings_says_so(signed_in, monkeypatch, use_settings):
    use_settings(smtp_pass="")
    response = signed_in.post("/api/share/email", json=EMAIL)
    assert response.status_code == 503
    assert "SMTP" in response.json()["message"]


def test_email_sends_one_message_per_address_with_the_pdf(signed_in, monkeypatch, use_settings):
    use_settings(smtp_pass="real-secret")
    sent = []

    async def fake_send(to, subject, text, attachments=None, reply_to=""):
        sent.append((to, subject, text, attachments))

    monkeypatch.setattr(mailer, "send_mail", fake_send)
    body = dict(EMAIL, to=["a@example.com", "b@example.com", "a@example.com"])
    response = signed_in.post("/api/share/email", json=body)

    assert response.status_code == 200, response.text
    assert [s[0] for s in sent] == ["a@example.com", "b@example.com"]
    to, subject, text, attachments = sent[0]
    assert subject == "Sailing schedule — Nhava Sheva to Italy"
    assert "2 sailing(s)" in text
    (filename, data, mime), = attachments
    assert filename.startswith("Sailing_Schedule_") and filename.endswith(".pdf")
    assert mime == "application/pdf" and data.startswith(b"%PDF-")


def test_email_with_nothing_to_send_is_refused(signed_in, fake_db, monkeypatch, use_settings):
    use_settings(smtp_pass="real-secret")
    fake_db.rows = []
    assert signed_in.post("/api/share/email", json=EMAIL).status_code == 422


def test_whatsapp_without_interakt_key_says_so(signed_in, monkeypatch, use_settings):
    use_settings(interakt_api_key="")
    response = signed_in.post("/api/share/whatsapp", json=WA)
    assert response.status_code == 503
    assert "Interakt" in response.json()["message"]


def test_whatsapp_sends_the_template_and_remembers_the_number(signed_in, fake_db, monkeypatch, tmp_path, use_settings):
    use_settings(interakt_api_key="real-key")
    use_settings(upload_dir=str(tmp_path))
    use_settings(public_url="https://sailing.example.com")
    calls = []

    async def fake_send(digits, pdf_url, file_name, body_values):
        calls.append((digits, pdf_url, file_name, body_values))

    monkeypatch.setattr(whatsapp, "send_template", fake_send)
    response = signed_in.post("/api/share/whatsapp", json=WA)

    assert response.status_code == 200, response.text
    (digits, url, file_name, values), = calls
    assert digits == "919867200083"
    assert url.startswith("https://sailing.example.com/shared/") and url.endswith(".pdf")
    assert values[0] == "Italy" and values[2] == "2"
    assert ("Buyer", "919867200083") in fake_db.wa_contacts

    # The link Interakt downloads works without a session, and serves the PDF.
    signed_in.cookies.clear()
    path = url.split("https://sailing.example.com")[1]
    served = signed_in.get(path)
    assert served.status_code == 200
    assert served.content.startswith(b"%PDF-")


def test_a_failed_whatsapp_send_does_not_remember_the_number(signed_in, fake_db, monkeypatch, tmp_path, use_settings):
    use_settings(interakt_api_key="real-key")
    use_settings(upload_dir=str(tmp_path))

    async def failing(*_):
        raise whatsapp.WhatsAppSendFailed("Interakt error 400: bad number")

    monkeypatch.setattr(whatsapp, "send_template", failing)
    response = signed_in.post("/api/share/whatsapp", json=WA)
    assert response.status_code == 502
    assert "Interakt error 400" in response.json()["message"]
    assert fake_db.wa_contacts == []


@pytest.mark.parametrize("name", ["nope.pdf", "....pdf", "a" * 50, ("x" * 43) + ".pdf"])
def test_shared_links_reject_unknown_or_malformed_names(client, monkeypatch, tmp_path, name, use_settings):
    use_settings(upload_dir=str(tmp_path))
    assert client.get(f"/shared/{name}").status_code == 404


@pytest.mark.parametrize("token", ["../../etc/passwd", "..", "a/b" * 20, "x" * 39, "x" * 65, "ab cd" * 10])
def test_only_well_formed_tokens_reach_the_disk(token, use_settings, tmp_path):
    use_settings(upload_dir=str(tmp_path))
    assert shared_pdfs.path_for(token) is None


def test_shared_links_expire(monkeypatch, tmp_path, use_settings):
    import os
    import time

    use_settings(upload_dir=str(tmp_path))
    token = shared_pdfs.save(b"%PDF-1.4")
    assert shared_pdfs.path_for(token) is not None
    old = time.time() - (shared_pdfs.KEEP_DAYS + 1) * 86400
    os.utime(shared_pdfs.path_for(token), (old, old))
    assert shared_pdfs.path_for(token) is None
    assert shared_pdfs.purge_old() == 1


def test_saved_numbers_list_and_save(signed_in, fake_db):
    assert signed_in.post("/api/wa-contacts", json={"name": "Buyer", "number": "98672 00083"}).status_code == 200
    assert signed_in.post("/api/wa-contacts", json={"name": "Again", "number": "+919867200083"}).status_code == 200
    assert fake_db.wa_contacts == [("Buyer", "919867200083")]
    assert signed_in.get("/api/wa-contacts").json()["data"] == [{"name": "Buyer", "number": "919867200083"}]

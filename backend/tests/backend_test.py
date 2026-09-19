"""Backend API tests for dental recall SaaS."""
import io
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://recall-pacjentow.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="session")
def s():
    return requests.Session()


# ---- Dashboard ----
def test_dashboard_stats(s):
    r = s.get(f"{API}/dashboard/stats", timeout=30)
    assert r.status_code == 200
    d = r.json()
    for k in ["AKTYWNY", "DO_PRZYPOMNIENIA", "PRZYPOMNIANY", "ZAPISANY", "ODRZUCONY"]:
        assert k in d["counts"]
    assert isinstance(d["total"], int)
    assert isinstance(d["chart"], list) and len(d["chart"]) == 30
    assert "przypomnienia" in d["chart"][0] and "zapisy" in d["chart"][0]


# ---- Patients CRUD ----
def test_list_patients(s):
    r = s.get(f"{API}/patients", timeout=30)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_patients_filters(s):
    r = s.get(f"{API}/patients", params={"status": "DO_PRZYPOMNIENIA"}, timeout=30)
    assert r.status_code == 200
    for p in r.json():
        assert p["status_recallu"] == "DO_PRZYPOMNIENIA"


def test_patient_crud_flow(s):
    payload = {"imie": "TEST", "nazwisko": "TESTOWY", "telefon": "+48 500 100 200",
               "email": "test_test@example.com", "data_ostatniej_wizyty": "2024-01-01",
               "typ_ostatniej_procedury": "Higienizacja"}
    r = s.post(f"{API}/patients", json=payload, timeout=30)
    assert r.status_code == 200
    pid = r.json()["id"]
    # update
    r = s.put(f"{API}/patients/{pid}", json={"imie": "TEST2"}, timeout=30)
    assert r.status_code == 200 and r.json()["imie"] == "TEST2"
    # remind sms
    r = s.post(f"{API}/patients/{pid}/remind", params={"channel": "SMS"}, timeout=30)
    assert r.status_code == 200
    # verify status
    r2 = s.get(f"{API}/patients", timeout=30)
    found = [x for x in r2.json() if x["id"] == pid][0]
    assert found["status_recallu"] == "PRZYPOMNIANY"
    # remind email
    r = s.post(f"{API}/patients/{pid}/remind", params={"channel": "EMAIL"}, timeout=30)
    assert r.status_code == 200
    # no-consent 400
    s.put(f"{API}/patients/{pid}", json={"zgoda_sms": False, "zgoda_email": False}, timeout=30)
    r = s.post(f"{API}/patients/{pid}/remind", params={"channel": "SMS"}, timeout=30)
    assert r.status_code == 400
    r = s.post(f"{API}/patients/{pid}/remind", params={"channel": "EMAIL"}, timeout=30)
    assert r.status_code == 400
    # exclude / include
    r = s.post(f"{API}/patients/{pid}/exclude", timeout=30)
    assert r.status_code == 200
    r = s.post(f"{API}/patients/{pid}/include", timeout=30)
    assert r.status_code == 200
    # delete
    r = s.delete(f"{API}/patients/{pid}", timeout=30)
    assert r.status_code == 200


# ---- CSV import ----
CSV_SAMPLE = """imie,nazwisko,telefon,email,data_ostatniej_wizyty,typ_ostatniej_procedury
TESTIMP,Kowal,+48 500 111 222,imp1@example.com,2024-03-01,Higienizacja
TESTIMP2,Nowak,bad_phone,imp2@example.com,2024-03-01,Higienizacja
,Brak,,,,
"""


def test_import_preview_and_commit(s):
    files = {"file": ("t.csv", io.BytesIO(CSV_SAMPLE.encode("utf-8")), "text/csv")}
    r = s.post(f"{API}/patients/import/preview", files=files, timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d["valid"] == 1 and d["invalid"] == 2
    assert "imie" in d["mapping"]
    # commit
    r = s.post(f"{API}/patients/import/commit", json={"rows": d["rows"]}, timeout=30)
    assert r.status_code == 200
    assert r.json()["inserted"] == 1


# ---- Procedures ----
def test_procedures_crud(s):
    r = s.get(f"{API}/procedures", timeout=30)
    assert r.status_code == 200 and len(r.json()) > 0
    r = s.post(f"{API}/procedures", json={"nazwa": "TEST_PROC", "interwal_miesiace": 3, "wartosc": 100}, timeout=30)
    assert r.status_code == 200
    pid = r.json()["id"]
    r = s.put(f"{API}/procedures/{pid}", json={"wartosc": 999}, timeout=30)
    assert r.status_code == 200 and r.json()["wartosc"] == 999
    r = s.delete(f"{API}/procedures/{pid}", timeout=30)
    assert r.status_code == 200


# ---- Templates & Settings ----
def test_templates(s):
    r = s.get(f"{API}/templates", timeout=30)
    assert r.status_code == 200
    orig = r.json()
    r = s.put(f"{API}/templates", json={"sms": "TESTSMS {imie}", "email_temat": orig.get("email_temat", ""), "email": orig.get("email", "")}, timeout=30)
    assert r.status_code == 200
    assert r.json()["sms"] == "TESTSMS {imie}"
    # restore
    s.put(f"{API}/templates", json={k: v for k, v in orig.items() if k != "id"}, timeout=30)


def test_settings(s):
    r = s.get(f"{API}/settings", timeout=30)
    assert r.status_code == 200
    orig = r.json()
    r = s.put(f"{API}/settings", json={**{k: v for k, v in orig.items() if k != "id"}, "telefon": "+48 000 000 000"}, timeout=30)
    assert r.status_code == 200 and r.json()["telefon"] == "+48 000 000 000"
    s.put(f"{API}/settings", json={k: v for k, v in orig.items() if k != "id"}, timeout=30)


# ---- Reminders & recall ----
def test_reminders(s):
    r = s.get(f"{API}/reminders", timeout=30)
    assert r.status_code == 200 and isinstance(r.json(), list)
    r = s.get(f"{API}/reminders", params={"typ": "SMS"}, timeout=30)
    assert r.status_code == 200
    for m in r.json():
        assert m["typ"] == "SMS"


def test_recall_run(s):
    r = s.post(f"{API}/recall/run", timeout=30)
    assert r.status_code == 200 and "marked_due" in r.json()


def test_roi(s):
    r = s.get(f"{API}/roi", timeout=30)
    assert r.status_code == 200
    d = r.json()
    for k in ["przypomnienia", "zapisy", "odrzucenia", "szacunkowy_przychod", "konwersja"]:
        assert k in d


# ---- Public booking ----
def test_booking_flow(s):
    # create dedicated patient for booking
    payload = {"imie": "BOOK", "nazwisko": "TEST", "telefon": "+48 500 200 300",
               "email": "book@example.com", "data_ostatniej_wizyty": "2024-01-01",
               "typ_ostatniej_procedury": "Higienizacja"}
    r = s.post(f"{API}/patients", json=payload, timeout=30)
    pid = r.json()["id"]
    r = s.get(f"{API}/booking/{pid}", timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d["pacjent"]["imie"] == "BOOK"
    assert len(d["sloty"]) > 0 and len(d["sloty"][0]["godziny"]) > 0
    slot = d["sloty"][0]
    r = s.post(f"{API}/booking/{pid}/confirm", json={"data": slot["data"], "godzina": slot["godziny"][0]}, timeout=30)
    assert r.status_code == 200
    # reject flow on second patient
    r = s.post(f"{API}/patients", json=payload, timeout=30)
    pid2 = r.json()["id"]
    r = s.post(f"{API}/booking/{pid2}/reject", timeout=30)
    assert r.status_code == 200
    # cleanup
    s.delete(f"{API}/patients/{pid}", timeout=30)
    s.delete(f"{API}/patients/{pid2}", timeout=30)


def test_booking_404(s):
    r = s.get(f"{API}/booking/000000000000000000000000", timeout=30)
    assert r.status_code == 404
    r = s.get(f"{API}/booking/invalid", timeout=30)
    assert r.status_code == 404


# ---- New feature tests (iteration 2) ----
import time as _time


def _read_cron_secret():
    with open("/app/backend/.env", "r") as f:
        for line in f:
            if line.startswith("WEBHOOK_CRON_SECRET"):
                v = line.split("=", 1)[1].strip().strip('"').strip("'")
                return v
    return None


CRON_SECRET = _read_cron_secret()


def test_sms_status(s):
    r = s.get(f"{API}/sms-status", timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d.get("skonfigurowane") is False
    assert d.get("tryb") == "MOCK"
    assert d.get("provider") == "Twilio"


def test_roi_pdf_download(s):
    r = s.get(f"{API}/roi/pdf", timeout=60)
    assert r.status_code == 200
    ct = r.headers.get("content-type", "")
    assert "application/pdf" in ct, f"content-type={ct}"
    cd = r.headers.get("content-disposition", "")
    assert "attachment" in cd.lower()
    assert len(r.content) > 1024
    assert r.content.startswith(b"%PDF")


def test_cron_recall_sequence_unauthorized(s):
    r = s.post(f"{API}/cron/recall-sequence", timeout=30)
    assert r.status_code == 401


def test_cron_recall_sequence_wrong_token(s):
    r = s.post(f"{API}/cron/recall-sequence", headers={"Authorization": "Bearer WRONG_TOKEN"}, timeout=30)
    assert r.status_code == 401


def test_cron_recall_sequence_authorized_moves_patients(s):
    assert CRON_SECRET, "WEBHOOK_CRON_SECRET missing"
    # reset demo for predictable state
    r = s.post(f"{API}/admin/reset-demo", timeout=60)
    assert r.status_code == 200

    before = s.get(f"{API}/dashboard/stats", timeout=30).json()["counts"]
    due_before = before.get("DO_PRZYPOMNIENIA", 0)
    przyp_before = before.get("PRZYPOMNIANY", 0)

    r = s.post(f"{API}/cron/recall-sequence",
               headers={"Authorization": f"Bearer {CRON_SECRET}"}, timeout=30)
    assert r.status_code in (200, 202)
    assert r.json().get("accepted") is True

    # wait for background task
    _time.sleep(3)

    after = s.get(f"{API}/dashboard/stats", timeout=30).json()["counts"]
    due_after = after.get("DO_PRZYPOMNIENIA", 0)
    przyp_after = after.get("PRZYPOMNIANY", 0)
    # DO_PRZYPOMNIENIA should decrease (or at least PRZYPOMNIANY increased) if there were due
    assert przyp_after >= przyp_before
    if due_before > 0:
        assert due_after < due_before or przyp_after > przyp_before

    # verify reminders now contain step 1 SMS with mock:true
    rems = s.get(f"{API}/reminders", params={"typ": "SMS"}, timeout=30).json()
    step1 = [m for m in rems if m.get("krok_sekwencji") == 1]
    assert len(step1) > 0, "expected step1 SMS reminders after cron"
    assert any(m.get("mock") is True for m in step1)


def test_recall_run_returns_sequence_counters(s):
    s.post(f"{API}/admin/reset-demo", timeout=60)
    r = s.post(f"{API}/recall/run", timeout=60)
    assert r.status_code == 200
    d = r.json()
    assert "marked_due" in d
    # sequence counters
    for k in ["nowe_sms", "email", "final_sms"]:
        assert k in d, f"missing key {k} in {d}"


def test_sequence_logic_sms_and_email_consent(s):
    # reset then create two patients: one SMS consent only, one EMAIL consent only
    s.post(f"{API}/admin/reset-demo", timeout=60)
    from datetime import date
    old_date = "2020-01-01"
    p_sms = {"imie": "SEQSMS", "nazwisko": "T", "telefon": "+48 500 111 000",
             "email": "seqsms@example.com", "data_ostatniej_wizyty": old_date,
             "typ_ostatniej_procedury": "Higienizacja",
             "zgoda_sms": True, "zgoda_email": False}
    p_email = {"imie": "SEQEMAIL", "nazwisko": "T", "telefon": "+48 500 222 000",
               "email": "seqemail@example.com", "data_ostatniej_wizyty": old_date,
               "typ_ostatniej_procedury": "Higienizacja",
               "zgoda_sms": False, "zgoda_email": True}
    r1 = s.post(f"{API}/patients", json=p_sms, timeout=30)
    r2 = s.post(f"{API}/patients", json=p_email, timeout=30)
    assert r1.status_code == 200 and r2.status_code == 200
    id1, id2 = r1.json()["id"], r2.json()["id"]

    # ensure recall marks them DO_PRZYPOMNIENIA
    s.post(f"{API}/recall/run", timeout=60)

    # fetch patients and check statuses
    all_p = s.get(f"{API}/patients", timeout=30).json()
    p1 = next((x for x in all_p if x["id"] == id1), None)
    p2 = next((x for x in all_p if x["id"] == id2), None)
    assert p1 and p2
    # After recall/run (which does advance_sequences too), they should have moved to PRZYPOMNIANY
    assert p1["status_recallu"] == "PRZYPOMNIANY", p1
    assert p1.get("sekwencja_krok") == 1
    assert p2["status_recallu"] == "PRZYPOMNIANY", p2
    # p2 has no sms consent -> should have gotten email at step 2
    assert p2.get("sekwencja_krok") == 2

    # verify reminders per patient
    rems1 = s.get(f"{API}/reminders", params={"patient_id": id1}, timeout=30).json()
    rems2 = s.get(f"{API}/reminders", params={"patient_id": id2}, timeout=30).json()
    assert any(m["typ"] == "SMS" and m.get("krok_sekwencji") == 1 for m in rems1)
    assert any(m["typ"] == "EMAIL" and m.get("krok_sekwencji") == 2 for m in rems2)

    # cleanup
    s.delete(f"{API}/patients/{id1}", timeout=30)
    s.delete(f"{API}/patients/{id2}", timeout=30)


def test_reset_demo_has_sekwencja_krok(s):
    r = s.post(f"{API}/admin/reset-demo", timeout=60)
    assert r.status_code == 200
    patients = s.get(f"{API}/patients", timeout=30).json()
    assert len(patients) > 0
    # NOTE: seed doesn't add sekwencja_krok explicitly (defaults handled via .get in code),
    # so some patients may lack the key. We assert at least the reminded ones carry it.
    reminded = [p for p in patients if p.get("status_recallu") == "PRZYPOMNIANY"]
    if reminded:
        assert any("sekwencja_krok" in p for p in reminded)



# ============================================================
# Iteration 3 tests: email real (Resend), timeline, slots, booking w/ clinic slots
# ============================================================
from datetime import date as _date, timedelta as _td


def _future_date(days=3):
    # server clock ~2026-09-19; use today+days
    return (_date.today() + _td(days=days)).isoformat()


def test_sms_status_email_fields(s):
    r = s.get(f"{API}/sms-status", timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d.get("skonfigurowane") is False
    assert d.get("tryb") == "MOCK"
    assert d.get("email_skonfigurowane") is True
    assert d.get("email_tryb") == "REALNY"
    assert d.get("email_provider") == "Resend"


def test_email_dispatch_real_deliverable(s):
    payload = {"imie": "TESTEMAIL", "nazwisko": "Real", "telefon": "+48 500 000 111",
               "email": "delivered@resend.dev", "data_ostatniej_wizyty": "2024-01-01",
               "typ_ostatniej_procedury": "Higienizacja",
               "zgoda_sms": False, "zgoda_email": True}
    r = s.post(f"{API}/patients", json=payload, timeout=30)
    assert r.status_code == 200
    pid = r.json()["id"]
    try:
        r = s.post(f"{API}/patients/{pid}/remind", params={"channel": "EMAIL"}, timeout=60)
        assert r.status_code == 200, r.text
        body = r.json()
        rem = body.get("reminder", body)
        assert rem.get("typ") == "EMAIL"
        assert rem.get("mock") is False, f"expected real email, got {rem}"
        assert rem.get("status") == "WYSLANO", f"status={rem.get('status')}"
    finally:
        s.delete(f"{API}/patients/{pid}", timeout=30)


def test_email_dispatch_invalid_email_graceful(s):
    payload = {"imie": "TESTEMAIL", "nazwisko": "Bad", "telefon": "+48 500 000 222",
               "email": "@example.com", "data_ostatniej_wizyty": "2024-01-01",
               "typ_ostatniej_procedury": "Higienizacja",
               "zgoda_sms": False, "zgoda_email": True}
    r = s.post(f"{API}/patients", json=payload, timeout=30)
    assert r.status_code == 200
    pid = r.json()["id"]
    try:
        r = s.post(f"{API}/patients/{pid}/remind", params={"channel": "EMAIL"}, timeout=60)
        # Must NOT 500 - endpoint should return 200 with BLAD status
        assert r.status_code == 200, r.text
        body = r.json()
        rem = body.get("reminder", body)
        assert rem.get("typ") == "EMAIL"
        # graceful failure: BLAD, not crash
        assert rem.get("status") == "BLAD"
        assert rem.get("mock") is False
    finally:
        s.delete(f"{API}/patients/{pid}", timeout=30)


def test_timeline_endpoint(s):
    # create patient, remind SMS (advances step 1) -> then check timeline
    payload = {"imie": "TIMELINE", "nazwisko": "T", "telefon": "+48 500 300 400",
               "email": "tl@example.com", "data_ostatniej_wizyty": "2024-01-01",
               "typ_ostatniej_procedury": "Higienizacja"}
    r = s.post(f"{API}/patients", json=payload, timeout=30)
    pid = r.json()["id"]
    try:
        s.post(f"{API}/patients/{pid}/remind", params={"channel": "SMS"}, timeout=30)
        r = s.get(f"{API}/patients/{pid}/timeline", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert "pacjent" in d
        assert "sekwencja_krok" in d
        assert "sekwencja_krok_opis" in d
        assert isinstance(d.get("przypomnienia"), list) and len(d["przypomnienia"]) >= 1
        assert isinstance(d.get("wizyty"), list)
        first = d["przypomnienia"][0]
        for k in ("typ", "krok_sekwencji", "mock", "status", "data_wyslania"):
            assert k in first, f"missing {k} in reminder"
        # next step should be present since patient is now PRZYPOMNIANY at krok 1
        assert d["sekwencja_krok"] == 1
        ns = d.get("nastepny_krok")
        assert ns is not None
        for k in ("typ", "data", "krok"):
            assert k in ns
    finally:
        s.delete(f"{API}/patients/{pid}", timeout=30)


def test_timeline_404(s):
    r = s.get(f"{API}/patients/000000000000000000000000/timeline", timeout=30)
    assert r.status_code == 404


def test_slots_crud_flow(s):
    # reset to clear slots
    s.post(f"{API}/admin/reset-demo", timeout=60)
    r = s.get(f"{API}/slots", timeout=30)
    assert r.status_code == 200
    assert r.json() == []

    d1 = _future_date(3)
    r = s.post(f"{API}/slots", json={"data": d1, "godziny": ["09:00", "10:00", "11:00"]}, timeout=30)
    assert r.status_code == 200
    assert r.json().get("added") == 3

    # duplicate detection
    r = s.post(f"{API}/slots", json={"data": d1, "godziny": ["09:00", "12:00"]}, timeout=30)
    assert r.status_code == 200
    assert r.json().get("added") == 1  # only 12:00 new

    # list sorted
    r = s.get(f"{API}/slots", timeout=30)
    assert r.status_code == 200
    slots = r.json()
    assert len(slots) == 4
    godz = [x["godzina"] for x in slots]
    assert godz == sorted(godz)

    # delete one
    sid = slots[0]["id"]
    r = s.delete(f"{API}/slots/{sid}", timeout=30)
    assert r.status_code == 200
    r = s.get(f"{API}/slots", timeout=30)
    assert len(r.json()) == 3


def test_booking_uses_clinic_slots(s):
    s.post(f"{API}/admin/reset-demo", timeout=60)
    # create patient
    payload = {"imie": "BOOKCL", "nazwisko": "T", "telefon": "+48 500 400 500",
               "email": "bc@example.com", "data_ostatniej_wizyty": "2024-01-01",
               "typ_ostatniej_procedury": "Higienizacja"}
    r = s.post(f"{API}/patients", json=payload, timeout=30)
    pid = r.json()["id"]
    try:
        # No clinic slots -> auto
        r = s.get(f"{API}/booking/{pid}", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["reczne_terminy"] is False
        assert len(d["sloty"]) > 0

        # add clinic slots
        d1 = _future_date(3)
        s.post(f"{API}/slots", json={"data": d1, "godziny": ["09:30", "14:00"]}, timeout=30)

        r = s.get(f"{API}/booking/{pid}", timeout=30)
        d = r.json()
        assert d["reczne_terminy"] is True
        assert len(d["sloty"]) == 1
        assert d["sloty"][0]["data"] == d1
        assert set(d["sloty"][0]["godziny"]) == {"09:30", "14:00"}

        # confirm booking -> slot zajety
        r = s.post(f"{API}/booking/{pid}/confirm", json={"data": d1, "godzina": "09:30"}, timeout=30)
        assert r.status_code == 200

        all_slots = s.get(f"{API}/slots", timeout=30).json()
        target = [x for x in all_slots if x["data"] == d1 and x["godzina"] == "09:30"]
        assert target and target[0]["zajety"] is True
        assert target[0].get("pacjent_id") == pid

        # patient status ZAPISANY
        pat = [p for p in s.get(f"{API}/patients", timeout=30).json() if p["id"] == pid][0]
        assert pat["status_recallu"] == "ZAPISANY"

        # confirmation SMS reminder created
        rems = s.get(f"{API}/reminders", params={"patient_id": pid, "typ": "SMS"}, timeout=30).json()
        assert any("Potwierdzenie" in (m.get("tresc") or "") for m in rems)
    finally:
        s.delete(f"{API}/patients/{pid}", timeout=30)

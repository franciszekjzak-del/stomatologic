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

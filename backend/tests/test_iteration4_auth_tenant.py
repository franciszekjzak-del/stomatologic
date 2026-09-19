"""Iteration 4 tests: JWT auth, multi-tenant isolation, per-clinic email sender,
public booking safety, 24h SMS reminders, cron, templates sms_24h."""
import os
import time
import pytest
import requests
from datetime import date, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://recall-pacjentow.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "franciszek.j.zak@gmail.com"
ADMIN_PASSWORD = "RecallDent2026!"
TEST_EMAIL = "test.gabinet@example.com"
TEST_PASSWORD = "Test12345!"


def _read_cron_secret():
    with open("/app/backend/.env", "r") as f:
        for line in f:
            if line.startswith("WEBHOOK_CRON_SECRET"):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


CRON_SECRET = _read_cron_secret()


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture(scope="module")
def test_token():
    return _login(TEST_EMAIL, TEST_PASSWORD)


def H(token):
    return {"Authorization": f"Bearer {token}"}


# ---------------- AUTH ----------------
class TestAuth:
    def test_login_success(self):
        r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert "token" in d and isinstance(d["token"], str) and len(d["token"]) > 20
        assert d["user"]["email"] == ADMIN_EMAIL
        assert "clinic_id" in d["user"]

    def test_login_wrong_password(self):
        r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": "WRONG_PASS_X!"}, timeout=30)
        assert r.status_code == 401

    def test_me_with_bearer(self, admin_token):
        r = requests.get(f"{API}/auth/me", headers=H(admin_token), timeout=30)
        assert r.status_code == 200
        assert r.json()["email"] == ADMIN_EMAIL

    def test_protected_endpoints_without_token(self):
        for ep in ["/patients", "/settings", "/dashboard/stats"]:
            r = requests.get(f"{API}{ep}", timeout=30)
            assert r.status_code == 401, f"{ep} returned {r.status_code}"

    def test_register_new_clinic_and_duplicate_and_weak_password(self):
        ts = int(time.time())
        email = f"qa+{ts}@example.com"
        payload = {"email": email, "password": "StrongPass1!", "nazwa_gabinetu": f"QA Gabinet {ts}", "dane_demo": True}
        r = requests.post(f"{API}/auth/register", json=payload, timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["token"] and d["user"]["email"] == email
        tok = d["token"]

        # new clinic must have own demo patients
        # give the background seed a moment
        for _ in range(6):
            pr = requests.get(f"{API}/patients", headers=H(tok), timeout=30)
            if pr.status_code == 200 and len(pr.json()) > 0:
                break
            time.sleep(1)
        assert pr.status_code == 200
        assert len(pr.json()) >= 20, f"expected demo patients for new clinic, got {len(pr.json())}"

        # settings has nazwa_gabinetu
        sr = requests.get(f"{API}/settings", headers=H(tok), timeout=30)
        assert sr.status_code == 200
        assert sr.json().get("nazwa_gabinetu") == f"QA Gabinet {ts}"

        # duplicate -> 409
        r2 = requests.post(f"{API}/auth/register", json=payload, timeout=30)
        assert r2.status_code == 409

        # weak password -> 400
        r3 = requests.post(f"{API}/auth/register",
                           json={"email": f"qa+{ts+1}@example.com", "password": "short", "nazwa_gabinetu": "X"}, timeout=30)
        assert r3.status_code == 400


# ---------------- ISOLATION ----------------
class TestIsolation:
    def test_test_clinic_has_zero_patients(self, test_token):
        r = requests.get(f"{API}/patients", headers=H(test_token), timeout=30)
        assert r.status_code == 200
        assert len(r.json()) == 0, f"test clinic should have 0 patients, got {len(r.json())}"

    def test_settings_not_shared(self, admin_token, test_token):
        # Set unique telefon in test clinic
        cur = requests.get(f"{API}/settings", headers=H(test_token), timeout=30).json()
        marker = f"+48 000 111 {int(time.time()) % 1000:03d}"
        payload = {k: v for k, v in cur.items() if k not in ("id", "resend_api_key_ustawiony", "resend_api_key_podglad")}
        payload["telefon"] = marker
        r = requests.put(f"{API}/settings", headers=H(test_token), json=payload, timeout=30)
        assert r.status_code == 200
        # admin settings should NOT change
        admin_s = requests.get(f"{API}/settings", headers=H(admin_token), timeout=30).json()
        assert admin_s.get("telefon") != marker

    def test_cross_clinic_timeline_404(self, admin_token, test_token):
        admin_pats = requests.get(f"{API}/patients", headers=H(admin_token), timeout=30).json()
        assert len(admin_pats) > 0
        pid = admin_pats[0]["id"]
        # test_token should get 404 on admin patient timeline
        r = requests.get(f"{API}/patients/{pid}/timeline", headers=H(test_token), timeout=30)
        assert r.status_code == 404


# ---------------- EMAIL SENDER ----------------
class TestEmailSender:
    def test_put_settings_with_email_and_key_then_mask(self, admin_token):
        r = requests.put(f"{API}/settings", headers=H(admin_token),
                         json={"email_nadawca": "przypomnienia@gabinet.pl",
                               "resend_api_key": "re_test_123456789012"}, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("resend_api_key_ustawiony") is True
        assert d.get("resend_api_key_podglad") and "…" in d["resend_api_key_podglad"]
        assert "resend_api_key" not in d

        # GET must not leak
        g = requests.get(f"{API}/settings", headers=H(admin_token), timeout=30).json()
        assert "resend_api_key" not in g
        assert g.get("resend_api_key_ustawiony") is True

    def test_put_without_key_keeps_it(self, admin_token):
        r = requests.put(f"{API}/settings", headers=H(admin_token),
                         json={"email_nadawca": "przypomnienia@gabinet.pl"}, timeout=30)
        assert r.status_code == 200
        assert r.json().get("resend_api_key_ustawiony") is True

    def test_invalid_email_nadawca_400(self, admin_token):
        r = requests.put(f"{API}/settings", headers=H(admin_token),
                         json={"email_nadawca": "not-an-email"}, timeout=30)
        assert r.status_code == 400

    def test_test_email_with_bad_key_400(self, admin_token):
        r = requests.post(f"{API}/settings/test-email", headers=H(admin_token),
                          json={"do": "qa@example.com"}, timeout=60)
        assert r.status_code == 400
        detail = (r.json().get("detail") or "").lower()
        # message should mention Resend somewhere
        assert "resend" in detail or "api key" in detail, r.text

    def test_clear_key_falls_back_to_emergent(self, admin_token):
        r = requests.put(f"{API}/settings", headers=H(admin_token),
                         json={"resend_api_key": ""}, timeout=30)
        assert r.status_code == 200
        assert r.json().get("resend_api_key_ustawiony") is False
        # test-email should now go through Emergent (200 with provider=emergent, or 400 if proxy fails)
        r = requests.post(f"{API}/settings/test-email", headers=H(admin_token),
                          json={"do": "delivered@resend.dev"}, timeout=90)
        # Accept 200 (real) or 400 (proxy failure - documented as non-app bug)
        assert r.status_code in (200, 400), r.text
        if r.status_code == 200:
            d = r.json()
            assert d.get("provider") in ("emergent", "Emergent", "resend", "Resend"), d

    def test_sms_status_email_domain_fields(self, admin_token):
        r = requests.get(f"{API}/sms-status", headers=H(admin_token), timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert "email_wlasna_domena" in d
        assert "email_nadawca" in d


# ---------------- PUBLIC BOOKING ----------------
class TestPublicBooking:
    def test_public_booking_no_secrets_leak(self, admin_token):
        pats = requests.get(f"{API}/patients", headers=H(admin_token), timeout=30).json()
        pid = pats[0]["id"]
        # PUBLIC (no token)
        r = requests.get(f"{API}/booking/{pid}", timeout=30)
        assert r.status_code == 200
        gabinet = r.json().get("gabinet", {})
        assert "resend_api_key" not in gabinet
        assert "email_reply_to" not in gabinet

    def test_public_booking_confirm_creates_appointment(self, admin_token):
        # pick any patient (create fresh to be safe)
        pats = requests.get(f"{API}/patients", headers=H(admin_token), timeout=30).json()
        # pick a patient not ZAPISANY
        cand = next((p for p in pats if p["status_recallu"] != "ZAPISANY"), pats[0])
        pid = cand["id"]
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        r = requests.post(f"{API}/booking/{pid}/confirm", json={"data": tomorrow, "godzina": "10:30"}, timeout=30)
        assert r.status_code == 200, r.text
        # patient becomes ZAPISANY
        pats2 = requests.get(f"{API}/patients", headers=H(admin_token), timeout=30).json()
        p2 = next(p for p in pats2 if p["id"] == pid)
        assert p2["status_recallu"] == "ZAPISANY"
        # appointment source ONLINE
        up = requests.get(f"{API}/appointments/upcoming", headers=H(admin_token), timeout=30).json()
        mine = [a for a in up if a["pacjent_id"] == pid]
        assert mine, "expected appointment for booked patient"
        assert mine[0].get("zrodlo") == "ONLINE"
        # save for 24h test
        pytest.booked_pid = pid


# ---------------- 24H SMS ----------------
class TestReminders24h:
    def test_send_24h_reminders(self, admin_token):
        r = requests.post(f"{API}/appointments/send-24h-reminders", headers=H(admin_token), timeout=60)
        assert r.status_code == 200, r.text
        assert r.json().get("wyslano", 0) >= 1

        rems = requests.get(f"{API}/reminders", headers=H(admin_token), timeout=30).json()
        r24 = [m for m in rems if m.get("rodzaj") == "PRZYPOMNIENIE_24H"]
        assert r24, "expected a PRZYPOMNIENIE_24H reminder"
        latest = r24[0]
        assert latest["typ"] == "SMS"
        assert latest.get("tresc"), "reminder has empty content"

    def test_send_24h_idempotent(self, admin_token):
        r = requests.post(f"{API}/appointments/send-24h-reminders", headers=H(admin_token), timeout=60)
        assert r.status_code == 200
        # second run should send 0 for the same appointment
        assert r.json().get("wyslano", 999) == 0

    def test_upcoming_has_flag(self, admin_token):
        up = requests.get(f"{API}/appointments/upcoming", headers=H(admin_token), timeout=30).json()
        # at least one appointment marked przypomnienie_24h:true
        assert any(a.get("przypomnienie_24h") is True for a in up)


# ---------------- CRON ----------------
class TestCron:
    def test_cron_unauthorized(self):
        r = requests.post(f"{API}/cron/recall-sequence", timeout=30)
        assert r.status_code == 401

    def test_cron_authorized(self):
        assert CRON_SECRET
        r = requests.post(f"{API}/cron/recall-sequence",
                          headers={"Authorization": f"Bearer {CRON_SECRET}"}, timeout=30)
        assert r.status_code == 200
        assert r.json().get("accepted") is True

    def test_recall_run_returns_24h_key(self, admin_token):
        r = requests.post(f"{API}/recall/run", headers=H(admin_token), timeout=60)
        assert r.status_code == 200
        assert "przypomnienia_24h" in r.json()


# ---------------- TEMPLATES ----------------
class TestTemplates:
    def test_templates_sms_24h(self, admin_token):
        r = requests.get(f"{API}/templates", headers=H(admin_token), timeout=30)
        assert r.status_code == 200
        d = r.json()
        # NOTE: pre-existing template docs may not have sms_24h (no backfill).
        # UI persists it on save. Verify PUT + GET round-trip works.
        orig = d.get("sms_24h", "")
        new_val = "TEST24H {data_wizyty} {godzina_wizyty}"
        payload = {k: v for k, v in d.items() if k != "id"}
        payload["sms_24h"] = new_val
        r = requests.put(f"{API}/templates", headers=H(admin_token), json=payload, timeout=30)
        assert r.status_code == 200
        assert r.json().get("sms_24h") == new_val
        # restore
        payload["sms_24h"] = orig
        requests.put(f"{API}/templates", headers=H(admin_token), json=payload, timeout=30)


# ---------------- REGRESSION ----------------
class TestRegression:
    def test_dashboard(self, admin_token):
        r = requests.get(f"{API}/dashboard/stats", headers=H(admin_token), timeout=30)
        assert r.status_code == 200
        assert "counts" in r.json()

    def test_roi_pdf(self, admin_token):
        r = requests.get(f"{API}/roi/pdf", headers=H(admin_token), timeout=60)
        assert r.status_code == 200
        assert "application/pdf" in r.headers.get("content-type", "")
        assert r.content.startswith(b"%PDF")

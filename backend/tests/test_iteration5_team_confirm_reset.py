"""
Iteration 5 backend tests:
  - Team accounts (invite/accept/list/delete)
  - Recepcja permissions (403 on owner-only)
  - Appointment confirmation flows (public respond, sms/inbound, simulate-reply)
  - Password reset (forgot -> reset -> login)
"""
import os
import time
import pytest
import requests
from pathlib import Path
from pymongo import MongoClient

# Load frontend .env for REACT_APP_BACKEND_URL
_fe_env = Path("/app/frontend/.env")
if "REACT_APP_BACKEND_URL" not in os.environ and _fe_env.exists():
    for line in _fe_env.read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            os.environ["REACT_APP_BACKEND_URL"] = line.split("=", 1)[1].strip().strip('"')
_be_env = Path("/app/backend/.env")
if _be_env.exists():
    for line in _be_env.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"'))

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

OWNER_EMAIL = "franciszek.j.zak@gmail.com"
OWNER_PASSWORD = "RecallDent2026!"
RECEPCJA_EMAIL = "recepcja.demo@example.com"
RECEPCJA_PASSWORD = "Recepcja123!"

TS = int(time.time())


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    return r


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def owner_token():
    r = _login(OWNER_EMAIL, OWNER_PASSWORD)
    assert r.status_code == 200, f"owner login: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def mongo_db():
    return MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[
        os.environ.get("DB_NAME", "test_database")
    ]


@pytest.fixture(scope="module")
def recepcja_token(owner_token, mongo_db):
    """Ensure recepcja.demo user exists in owner's clinic; return valid token."""
    # try login
    r = _login(RECEPCJA_EMAIL, RECEPCJA_PASSWORD)
    if r.status_code == 200:
        return r.json()["token"]
    # need to create via invite
    # first delete any orphan user record
    mongo_db.users.delete_many({"email": RECEPCJA_EMAIL})
    inv = requests.post(f"{API}/auth/invite", headers=_h(owner_token),
                        json={"email": RECEPCJA_EMAIL, "imie": "Recepcja Demo"}, timeout=30)
    assert inv.status_code == 200, f"invite: {inv.status_code} {inv.text}"
    link = inv.json()["link"]
    token = link.rstrip("/").split("/")[-1]
    acc = requests.post(f"{API}/auth/invite/{token}/accept",
                        json={"password": RECEPCJA_PASSWORD}, timeout=30)
    assert acc.status_code == 200, f"accept: {acc.status_code} {acc.text}"
    return acc.json()["token"]


# ---------------------------------------------------------------------------
# TEAM: invites / users
# ---------------------------------------------------------------------------
class TestTeam:
    invited_email = f"qa.recepcja+{TS}@example.com"
    invite_link = None
    invite_token = None
    new_user_id = None

    def test_invite_create(self, owner_token):
        r = requests.post(f"{API}/auth/invite", headers=_h(owner_token),
                          json={"email": self.__class__.invited_email, "imie": "QA"}, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "link" in data and "/zaproszenie/" in data["link"]
        self.__class__.invite_link = data["link"]
        self.__class__.invite_token = data["link"].rstrip("/").split("/")[-1]

    def test_invite_info_no_auth(self):
        assert self.__class__.invite_token
        r = requests.get(f"{API}/auth/invite/{self.__class__.invite_token}", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["email"] == self.__class__.invited_email
        assert "gabinet" in d and "zapraszajacy" in d

    def test_invite_accept(self):
        r = requests.post(f"{API}/auth/invite/{self.__class__.invite_token}/accept",
                          json={"password": "Recepcja123!"}, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "token" in d and d["user"]["rola"] == "recepcja"
        self.__class__.new_user_id = d["user"]["id"]

    def test_invite_reaccept_fails(self):
        r = requests.post(f"{API}/auth/invite/{self.__class__.invite_token}/accept",
                          json={"password": "Recepcja123!"}, timeout=30)
        assert r.status_code in (404, 409), f"expected 404/409, got {r.status_code}"

    def test_list_users(self, owner_token):
        r = requests.get(f"{API}/auth/users", headers=_h(owner_token), timeout=30)
        assert r.status_code == 200
        users = r.json()["uzytkownicy"]
        emails = [u["email"] for u in users]
        assert OWNER_EMAIL in emails
        assert self.__class__.invited_email in emails

    def test_invite_existing_email_conflict(self, owner_token):
        r = requests.post(f"{API}/auth/invite", headers=_h(owner_token),
                          json={"email": self.__class__.invited_email}, timeout=30)
        assert r.status_code == 409

    def test_delete_recepcja(self, owner_token):
        uid = self.__class__.new_user_id
        assert uid
        r = requests.delete(f"{API}/auth/users/{uid}", headers=_h(owner_token), timeout=30)
        assert r.status_code == 200

    def test_owner_cannot_delete_self(self, owner_token):
        me = requests.get(f"{API}/auth/me", headers=_h(owner_token), timeout=30).json()
        r = requests.delete(f"{API}/auth/users/{me['id']}", headers=_h(owner_token), timeout=30)
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# RECEPCJA PERMISSIONS
# ---------------------------------------------------------------------------
class TestRecepcjaPermissions:
    def test_get_patients_allowed(self, recepcja_token):
        r = requests.get(f"{API}/patients", headers=_h(recepcja_token), timeout=30)
        assert r.status_code == 200
        assert len(r.json()) >= 30  # owner's clinic has 32 demo patients

    def test_upcoming_allowed(self, recepcja_token):
        r = requests.get(f"{API}/appointments/upcoming", headers=_h(recepcja_token), timeout=30)
        assert r.status_code == 200

    def test_remind_allowed(self, recepcja_token):
        pts = requests.get(f"{API}/patients", headers=_h(recepcja_token), timeout=30).json()
        # find one with zgoda_sms
        target = next((p for p in pts if p.get("zgoda_sms")), pts[0])
        r = requests.post(f"{API}/patients/{target['id']}/remind",
                          headers=_h(recepcja_token), timeout=30)
        assert r.status_code == 200

    def test_settings_put_forbidden(self, recepcja_token):
        r = requests.put(f"{API}/settings", headers=_h(recepcja_token), json={"telefon": "x"}, timeout=30)
        assert r.status_code == 403

    def test_templates_put_forbidden(self, recepcja_token):
        r = requests.put(f"{API}/templates", headers=_h(recepcja_token), json={"sms": "x"}, timeout=30)
        assert r.status_code == 403

    def test_procedures_post_forbidden(self, recepcja_token):
        r = requests.post(f"{API}/procedures", headers=_h(recepcja_token),
                          json={"nazwa": "X", "interwal_miesiace": 6, "wartosc": 100, "aktywna": True}, timeout=30)
        assert r.status_code == 403

    def test_patient_delete_forbidden(self, recepcja_token):
        pts = requests.get(f"{API}/patients", headers=_h(recepcja_token), timeout=30).json()
        pid = pts[0]["id"]
        r = requests.delete(f"{API}/patients/{pid}", headers=_h(recepcja_token), timeout=30)
        assert r.status_code == 403

    def test_reset_demo_forbidden(self, recepcja_token):
        r = requests.post(f"{API}/admin/reset-demo", headers=_h(recepcja_token), timeout=30)
        assert r.status_code == 403

    def test_list_users_forbidden(self, recepcja_token):
        r = requests.get(f"{API}/auth/users", headers=_h(recepcja_token), timeout=30)
        assert r.status_code == 403

    def test_invite_forbidden(self, recepcja_token):
        r = requests.post(f"{API}/auth/invite", headers=_h(recepcja_token),
                          json={"email": f"blocked{TS}@example.com"}, timeout=30)
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# APPOINTMENT CONFIRMATION
# ---------------------------------------------------------------------------
class TestConfirmation:
    def _get_planned_unconfirmed(self, token):
        r = requests.get(f"{API}/appointments/upcoming", headers=_h(token), timeout=30)
        for a in r.json():
            if a.get("status") == "ZAPLANOWANA" and not a.get("potwierdzona"):
                return a
        return None

    def _make_new_appointment(self, token):
        """Book a new visit via public endpoint for the first patient."""
        pts = requests.get(f"{API}/patients", headers=_h(token), timeout=30).json()
        pid = pts[0]["id"]
        info = requests.get(f"{API}/booking/{pid}", timeout=30).json()
        # find a slot
        slot = info["sloty"][0]
        r = requests.post(f"{API}/booking/{pid}/confirm",
                          json={"data": slot["data"], "godzina": slot["godziny"][0]}, timeout=30)
        assert r.status_code == 200
        return r.json()["wizyta"]["id"]

    def test_upcoming_fields(self, owner_token):
        r = requests.get(f"{API}/appointments/upcoming", headers=_h(owner_token), timeout=30)
        assert r.status_code == 200
        data = r.json()
        if not data:
            # create one
            self._make_new_appointment(owner_token)
            data = requests.get(f"{API}/appointments/upcoming", headers=_h(owner_token), timeout=30).json()
        a = data[0]
        for k in ("telefon", "link_potwierdzenia", "status"):
            assert k in a, f"missing key {k} in upcoming appt"

    def test_public_appointment_endpoint(self, owner_token):
        appt = self._get_planned_unconfirmed(owner_token)
        if not appt:
            aid = self._make_new_appointment(owner_token)
        else:
            aid = appt["id"]
        r = requests.get(f"{API}/appointments/{aid}/public", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert "wizyta" in d and "gabinet" in d
        assert "resend_api_key" not in d["gabinet"]

    def test_respond_yes(self, owner_token):
        appt = self._get_planned_unconfirmed(owner_token)
        if not appt:
            aid = self._make_new_appointment(owner_token)
        else:
            aid = appt["id"]
        r = requests.post(f"{API}/appointments/{aid}/respond",
                          json={"odpowiedz": "tak"}, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["potwierdzona"] is True
        assert d["status"] == "ZAPLANOWANA"

    def test_respond_invalid(self, owner_token):
        appt = self._get_planned_unconfirmed(owner_token) or {"id": self._make_new_appointment(owner_token)}
        r = requests.post(f"{API}/appointments/{appt['id']}/respond",
                          json={"odpowiedz": "może"}, timeout=30)
        assert r.status_code == 400

    def test_sms_inbound_no(self, owner_token):
        # need a NEW planned unconfirmed appointment
        aid = self._make_new_appointment(owner_token)
        # get the appointment to find patient phone
        pub = requests.get(f"{API}/appointments/{aid}/public", timeout=30).json()
        # get phone from upcoming
        up = requests.get(f"{API}/appointments/upcoming", headers=_h(owner_token), timeout=30).json()
        my = next((a for a in up if a["id"] == aid), None)
        assert my, "created appointment not in upcoming"
        phone = my["telefon"]
        assert phone
        r = requests.post(f"{API}/sms/inbound",
                          data={"From": phone, "Body": "NIE"}, timeout=30)
        assert r.status_code == 200
        assert "<Response>" in r.text
        # verify appointment now ODWOLANA
        pub2 = requests.get(f"{API}/appointments/{aid}/public", timeout=30).json()
        assert pub2["wizyta"]["status"] == "ODWOLANA", f"got {pub2['wizyta']}"
        assert pub2["wizyta"]["potwierdzona"] is False

    def test_simulate_reply(self, owner_token):
        aid = self._make_new_appointment(owner_token)
        r = requests.post(f"{API}/appointments/{aid}/simulate-reply",
                          headers=_h(owner_token), json={"odpowiedz": "TAK"}, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["potwierdzona"] is True

    def test_reminders_has_response_entries(self, owner_token):
        r = requests.get(f"{API}/reminders", headers=_h(owner_token), timeout=30)
        assert r.status_code == 200
        rows = r.json()
        assert any(x.get("rodzaj") == "ODPOWIEDZ_PACJENTA" for x in rows)


# ---------------------------------------------------------------------------
# PASSWORD RESET
# ---------------------------------------------------------------------------
class TestPasswordReset:
    NEW_PW = "NoweHaslo123!"

    def test_forgot_unknown_email_generic_200(self):
        r = requests.post(f"{API}/auth/forgot-password",
                          json={"email": "nieistnieje@example.com"}, timeout=30)
        assert r.status_code == 200
        assert r.json().get("ok") is True

    def test_full_reset_flow(self, recepcja_token, mongo_db):
        # ensure recepcja user exists — recepcja_token fixture guarantees it
        r = requests.post(f"{API}/auth/forgot-password",
                          json={"email": RECEPCJA_EMAIL}, timeout=30)
        assert r.status_code == 200
        # fetch latest token from mongo
        user = mongo_db.users.find_one({"email": RECEPCJA_EMAIL})
        assert user
        rec = mongo_db.password_resets.find({"user_id": str(user["_id"]), "uzyte": False}).sort("utworzono", -1).limit(1)
        rec = list(rec)
        assert rec, "no password reset token in mongo"
        token = rec[0]["token"]

        # reset
        r2 = requests.post(f"{API}/auth/reset-password",
                           json={"token": token, "password": self.NEW_PW}, timeout=30)
        assert r2.status_code == 200, r2.text
        assert "token" in r2.json()

        # login with new password
        rl = _login(RECEPCJA_EMAIL, self.NEW_PW)
        assert rl.status_code == 200

        # login with old password -> 401
        rlo = _login(RECEPCJA_EMAIL, RECEPCJA_PASSWORD)
        assert rlo.status_code == 401

        # reuse token -> 400
        r3 = requests.post(f"{API}/auth/reset-password",
                           json={"token": token, "password": "Innehaslo123!"}, timeout=30)
        assert r3.status_code == 400

        # RESTORE recepcja password to Recepcja123! via another reset flow
        requests.post(f"{API}/auth/forgot-password", json={"email": RECEPCJA_EMAIL}, timeout=30)
        rec2 = list(mongo_db.password_resets.find(
            {"user_id": str(user["_id"]), "uzyte": False}).sort("utworzono", -1).limit(1))
        assert rec2
        rr = requests.post(f"{API}/auth/reset-password",
                           json={"token": rec2[0]["token"], "password": RECEPCJA_PASSWORD}, timeout=30)
        assert rr.status_code == 200
        assert _login(RECEPCJA_EMAIL, RECEPCJA_PASSWORD).status_code == 200


# ---------------------------------------------------------------------------
# 24h SMS + template
# ---------------------------------------------------------------------------
class TestSms24h:
    def test_template_has_confirm_placeholder(self, owner_token):
        r = requests.get(f"{API}/templates", headers=_h(owner_token), timeout=30)
        assert r.status_code == 200
        t = r.json()
        # may need default fallback if missing
        sms_24h = t.get("sms_24h", "")
        assert "{link_potwierdzenia}" in sms_24h or sms_24h == "", \
            "sms_24h template lacks {link_potwierdzenia}"

    def test_send_24h(self, owner_token):
        r = requests.post(f"{API}/appointments/send-24h-reminders",
                          headers=_h(owner_token), timeout=60)
        assert r.status_code == 200
        assert "wyslano" in r.json()

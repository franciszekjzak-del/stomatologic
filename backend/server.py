from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File, Header, BackgroundTasks, Depends
from fastapi.responses import Response
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import io
import csv
import re
import hmac
import logging
import random
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
from bson import ObjectId
from datetime import datetime, timezone, timedelta, date

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
raw_db = client[os.environ['DB_NAME']]

from tenant import TenantDB, set_clinic, get_clinic
import auth

db = TenantDB(raw_db)

app = FastAPI()
public_router = APIRouter(prefix="/api")
api_router = APIRouter(prefix="/api", dependencies=[Depends(auth.require_clinic)])


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.isoformat()


# Recall statuses
STATUS_ACTIVE = "AKTYWNY"
STATUS_DUE = "DO_PRZYPOMNIENIA"
STATUS_REMINDED = "PRZYPOMNIANY"
STATUS_BOOKED = "ZAPISANY"
STATUS_REJECTED = "ODRZUCONY"

PHONE_RE = re.compile(r"^\+?[0-9\s\-]{9,15}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Sequence steps: 0 = not started, 1 = initial SMS sent, 2 = follow-up email sent,
# 3 = final SMS reminder sent (sequence finished)
SEQ_GAP_DAYS = {1: 3, 2: 7}  # after step1 wait 3 days -> email; after step2 wait 7 days -> final SMS


# ---------------------------------------------------------------------------
# SMS gateway (Twilio) with graceful MOCK fallback
# ---------------------------------------------------------------------------
def twilio_configured() -> bool:
    return all(os.environ.get(k) for k in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_PHONE_NUMBER"))


def send_sms(to: str, body: str) -> dict:
    """Send an SMS via Twilio if configured, else return a MOCK result.
    Returns dict: {status, mock, error}."""
    if not to:
        return {"status": "BLAD", "mock": not twilio_configured(), "error": "brak numeru"}
    if not twilio_configured():
        return {"status": "WYSLANO", "mock": True, "error": None}
    try:
        from twilio.rest import Client
        client = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
        msg = client.messages.create(
            from_=os.environ["TWILIO_PHONE_NUMBER"],
            to=to.replace(" ", ""),
            body=body,
        )
        return {"status": "WYSLANO", "mock": False, "error": None, "sid": msg.sid}
    except Exception as e:
        logging.getLogger(__name__).error("Twilio send error: %s", e)
        return {"status": "BLAD", "mock": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Email gateway (Emergent-managed Resend) with graceful MOCK fallback
# ---------------------------------------------------------------------------
import httpx
from html import escape as _html_escape

EMAIL_BASE_URL = "https://integrations.emergentagent.com"


def email_configured() -> bool:
    return bool(os.environ.get("EMERGENT_EMAIL_KEY"))


def app_base_url() -> str:
    return os.environ.get("APP_BASE_URL", "").rstrip("/")


def booking_link(pid: str) -> str:
    base = app_base_url()
    return f"{base}/zapis/{pid}" if base else f"/zapis/{pid}"


def _email_html(patient: dict, body_text: str, link: str, clinic: str) -> str:
    safe_body = _html_escape(body_text).replace("\n", "<br>")
    return (
        '<table role="presentation" width="100%" style="background:#F9FAFB;padding:24px">'
        '<tr><td align="center">'
        '<table role="presentation" width="560" style="background:#FFFFFF;border-radius:12px;'
        'border:1px solid #E5E7EB;font-family:Arial,Helvetica,sans-serif">'
        '<tr><td style="background:#2D6A4F;border-radius:12px 12px 0 0;padding:20px 28px">'
        f'<span style="color:#FFFFFF;font-size:18px;font-weight:bold">{_html_escape(clinic)}</span>'
        '</td></tr>'
        '<tr><td style="padding:28px">'
        f'<p style="color:#1C1917;font-size:15px;line-height:1.6;margin:0 0 24px">{safe_body}</p>'
        f'<a href="{link}" style="display:inline-block;background:#2D6A4F;color:#FFFFFF;'
        'text-decoration:none;padding:12px 24px;border-radius:8px;font-size:15px;font-weight:bold">'
        'Zarezerwuj wizytę</a>'
        '</td></tr>'
        '<tr><td style="padding:0 28px 24px">'
        f'<p style="color:#888;font-size:12px;line-height:1.5;margin:16px 0 0">Wiadomość wysłana przez '
        f'{_html_escape(clinic)} w ramach przypomnienia o wizycie kontrolnej. Nigdy nie prosimy '
        'o hasło ani dane karty w wiadomości email.</p>'
        '</td></tr></table></td></tr></table>'
    )


async def send_email_reminder(to: str, subject: str, html: str, settings: Optional[dict] = None) -> dict:
    """Send email: own Resend domain (clinic settings) if configured, else Emergent-managed proxy; MOCK fallback."""
    if not to:
        return {"status": "BLAD", "mock": not email_configured(), "error": "brak adresu email"}
    settings = settings or {}
    own_key = (settings.get("resend_api_key") or "").strip()
    own_from = (settings.get("email_nadawca") or "").strip()
    from_name = settings.get("nazwa_gabinetu") or os.environ.get("EMAIL_FROM_NAME", "RecallDent")
    reply_to = (settings.get("email_reply_to") or os.environ.get("EMAIL_REPLY_TO") or "").strip()
    try:
        if own_key and own_from:
            payload = {"from": f"{from_name} <{own_from}>", "to": [to], "subject": subject, "html": html}
            if reply_to:
                payload["reply_to"] = reply_to
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post("https://api.resend.com/emails",
                                         headers={"Authorization": f"Bearer {own_key}"}, json=payload)
            if resp.status_code >= 400:
                detail = resp.json().get("message", resp.text) if resp.headers.get("content-type", "").startswith("application/json") else resp.text
                return {"status": "BLAD", "mock": False, "error": f"Resend: {detail}", "provider": "resend_own"}
            return {"status": "WYSLANO", "mock": False, "error": None, "id": resp.json().get("id"), "provider": "resend_own"}
        if not email_configured():
            return {"status": "WYSLANO", "mock": True, "error": None}
        payload = {"to": [to], "subject": subject, "html": html, "from_name": from_name}
        if reply_to:
            payload["contact_email"] = reply_to
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{EMAIL_BASE_URL}/api/v1/email/send",
                headers={"X-Email-Key": os.environ["EMERGENT_EMAIL_KEY"]},
                json=payload,
            )
        resp.raise_for_status()
        return {"status": "WYSLANO", "mock": False, "error": None, "id": resp.json().get("id"), "provider": "emergent"}
    except Exception as e:
        logging.getLogger(__name__).error("Email send error: %s", e)
        return {"status": "BLAD", "mock": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class Patient(BaseModel):
    imie: str
    nazwisko: str
    telefon: str = ""
    email: str = ""
    data_ostatniej_wizyty: str = ""
    typ_ostatniej_procedury: str = ""
    status_recallu: str = STATUS_ACTIVE
    data_ostatniego_przypomnienia: Optional[str] = None
    sekwencja_krok: int = 0
    zgoda_sms: bool = True
    zgoda_email: bool = True
    wykluczony: bool = False
    utworzono: str = Field(default_factory=lambda: iso(now_utc()))
    zaktualizowano: str = Field(default_factory=lambda: iso(now_utc()))


class PatientCreate(BaseModel):
    imie: str
    nazwisko: str
    telefon: str = ""
    email: str = ""
    data_ostatniej_wizyty: str = ""
    typ_ostatniej_procedury: str = ""
    zgoda_sms: bool = True
    zgoda_email: bool = True


class PatientUpdate(BaseModel):
    imie: Optional[str] = None
    nazwisko: Optional[str] = None
    telefon: Optional[str] = None
    email: Optional[str] = None
    data_ostatniej_wizyty: Optional[str] = None
    typ_ostatniej_procedury: Optional[str] = None
    zgoda_sms: Optional[bool] = None
    zgoda_email: Optional[bool] = None


class Procedure(BaseModel):
    nazwa: str
    interwal_miesiace: int = 6
    wartosc: int = 200
    aktywna: bool = True


class ProcedureUpdate(BaseModel):
    nazwa: Optional[str] = None
    interwal_miesiace: Optional[int] = None
    wartosc: Optional[int] = None
    aktywna: Optional[bool] = None


def clean(doc: dict) -> dict:
    if not doc:
        return doc
    doc = dict(doc)
    if "_id" in doc:
        doc["id"] = str(doc["_id"])
        del doc["_id"]
    return doc


# ---------------------------------------------------------------------------
# Seed defaults
# ---------------------------------------------------------------------------
DEFAULT_PROCEDURES = [
    {"nazwa": "Higienizacja", "interwal_miesiace": 6, "wartosc": 250, "aktywna": True},
    {"nazwa": "Kontrola / Przegląd", "interwal_miesiace": 12, "wartosc": 150, "aktywna": True},
    {"nazwa": "Leczenie kanałowe", "interwal_miesiace": 6, "wartosc": 1500, "aktywna": True},
    {"nazwa": "Wybielanie", "interwal_miesiace": 12, "wartosc": 800, "aktywna": True},
    {"nazwa": "Wypełnienie", "interwal_miesiace": 6, "wartosc": 350, "aktywna": True},
]

DEFAULT_SETTINGS = {
    "nazwa_gabinetu": "Gabinet Stomatologiczny DentaMed",
    "adres": "ul. Kwiatowa 12, 00-001 Warszawa",
    "telefon": "+48 22 123 45 67",
    "logo_url": "",
    "godzina_od": 10,
    "godzina_do": 18,
    "plan": "Rozszerzony",
    "email_nadawca": "",
    "resend_api_key": "",
    "email_reply_to": "",
}

DEFAULT_TEMPLATES = {
    "sms": "Pacjent {imie}, minęło {interwal} od ostatniej wizyty ({procedura}). Zarezerwuj wizytę kontrolną: {link_do_zapisu} — {nazwa_gabinetu}",
    "email_temat": "Czas na wizytę kontrolną w {nazwa_gabinetu}",
    "email": "Dzień dobry {imie} {nazwisko},\n\nminęło {interwal} od Twojej ostatniej wizyty ({procedura}). Zapraszamy na wizytę kontrolną.\n\nZarezerwuj termin online: {link_do_zapisu}\n\nPozdrawiamy,\n{nazwa_gabinetu}",
    "sms_24h": "Przypominamy: jutro {data_wizyty} o {godzina_wizyty} masz wizytę w {nazwa_gabinetu}, {adres}. W razie zmiany planów prosimy o kontakt: {telefon_gabinetu}.",
}

IMIONA_M = ["Jan", "Piotr", "Andrzej", "Tomasz", "Marcin", "Michał", "Krzysztof", "Paweł", "Adam", "Jakub"]
IMIONA_K = ["Anna", "Maria", "Katarzyna", "Agnieszka", "Barbara", "Ewa", "Magdalena", "Joanna", "Zofia", "Julia"]
NAZWISKA = ["Nowak", "Kowalski", "Wiśniewski", "Wójcik", "Kowalczyk", "Kamiński", "Lewandowski", "Zieliński",
            "Szymański", "Woźniak", "Dąbrowski", "Kozłowski", "Jankowski", "Mazur", "Kwiatkowski"]


async def seed_if_empty(demo: bool = True, nazwa: Optional[str] = None):
    """Seed defaults for the clinic in the current tenant context."""
    if await db.procedures.count_documents({}) == 0:
        await db.procedures.insert_many([dict(p) for p in DEFAULT_PROCEDURES])
    if await db.settings.count_documents({}) == 0:
        s = dict(DEFAULT_SETTINGS)
        if nazwa:
            s["nazwa_gabinetu"] = nazwa
            s["adres"] = ""
            s["telefon"] = ""
        await db.settings.insert_one(s)
    if await db.templates.count_documents({}) == 0:
        await db.templates.insert_one(dict(DEFAULT_TEMPLATES))
    if demo and await db.patients.count_documents({}) == 0:
        procs = await db.procedures.find({}).to_list(100)
        patients = []
        for i in range(32):
            female = random.random() > 0.5
            imie = random.choice(IMIONA_K if female else IMIONA_M)
            nazwisko = random.choice(NAZWISKA)
            proc = random.choice(procs)
            months_ago = random.randint(2, 14)
            last_visit = (now_utc() - timedelta(days=months_ago * 30)).date()
            patients.append({
                "imie": imie,
                "nazwisko": nazwisko,
                "telefon": f"+48 {random.randint(500,899)} {random.randint(100,999)} {random.randint(100,999)}",
                "email": f"{imie.lower()}.{nazwisko.lower()}{i}@example.com",
                "data_ostatniej_wizyty": last_visit.isoformat(),
                "typ_ostatniej_procedury": proc["nazwa"],
                "status_recallu": STATUS_ACTIVE,
                "data_ostatniego_przypomnienia": None,
                "sekwencja_krok": 0,
                "zgoda_sms": random.random() > 0.15,
                "zgoda_email": random.random() > 0.3,
                "wykluczony": False,
                "utworzono": iso(now_utc()),
                "zaktualizowano": iso(now_utc()),
            })
        await db.patients.insert_many(patients)
        await run_recall_scan()
        due = await db.patients.find({"status_recallu": STATUS_DUE}).to_list(100)
        random.shuffle(due)
        n = len(due)
        n_book = max(1, int(n * 0.18))
        n_reject = max(1, int(n * 0.12))
        n_remind = max(1, int(n * 0.30))
        # leave the remaining ~40% as DO_PRZYPOMNIENIA for the demo dashboard
        for idx, p in enumerate(due):
            if idx < n_book:
                await _send_reminder(p, channel="SMS", historical=True)
                await _create_appointment(p, when=now_utc() + timedelta(days=random.randint(1, 20)), historical=True)
            elif idx < n_book + n_reject:
                await _send_reminder(p, channel="SMS", historical=True)
                await db.patients.update_one({"_id": p["_id"]}, {"$set": {"status_recallu": STATUS_REJECTED}})
            elif idx < n_book + n_reject + n_remind:
                channel = "EMAIL" if idx % 3 == 0 else "SMS"
                await _send_reminder(p, channel=channel, historical=True)


# ---------------------------------------------------------------------------
# Recall engine
# ---------------------------------------------------------------------------
def interval_label(months: int) -> str:
    if months == 1:
        return "1 miesiąc"
    if months < 5:
        return f"{months} miesiące"
    if months == 12:
        return "rok"
    return f"{months} miesięcy"


async def run_recall_scan() -> int:
    procs = {p["nazwa"]: p for p in await db.procedures.find({}).to_list(100)}
    marked = 0
    today = now_utc().date()
    cursor = db.patients.find({"wykluczony": False, "status_recallu": STATUS_ACTIVE})
    async for p in cursor:
        proc = procs.get(p.get("typ_ostatniej_procedury"))
        if not proc or not proc.get("aktywna", True):
            continue
        lv = p.get("data_ostatniej_wizyty")
        if not lv:
            continue
        try:
            lv_date = date.fromisoformat(lv[:10])
        except Exception:
            continue
        due_date = lv_date + timedelta(days=proc["interwal_miesiace"] * 30)
        if due_date <= today:
            await db.patients.update_one(
                {"_id": p["_id"]},
                {"$set": {"status_recallu": STATUS_DUE, "zaktualizowano": iso(now_utc())}},
            )
            marked += 1
    return marked


def render_template(tpl: str, patient: dict, proc: Optional[dict], settings: dict, link: str) -> str:
    interval = interval_label(proc["interwal_miesiace"]) if proc else "6 miesięcy"
    return (tpl
            .replace("{imie}", patient.get("imie", ""))
            .replace("{nazwisko}", patient.get("nazwisko", ""))
            .replace("{procedura}", patient.get("typ_ostatniej_procedury", ""))
            .replace("{interwal}", interval)
            .replace("{link_do_zapisu}", link)
            .replace("{nazwa_gabinetu}", settings.get("nazwa_gabinetu", "")))


async def _send_reminder(patient: dict, channel: str = "SMS", historical: bool = False, seq_step: Optional[int] = None):
    settings = await db.settings.find_one({}) or DEFAULT_SETTINGS
    templates = await db.templates.find_one({}) or DEFAULT_TEMPLATES
    procs = {p["nazwa"]: p for p in await db.procedures.find({}).to_list(100)}
    proc = procs.get(patient.get("typ_ostatniej_procedury"))
    pid = str(patient["_id"])
    link = booking_link(pid)
    clinic = settings.get("nazwa_gabinetu", "")
    if channel == "EMAIL":
        tresc = render_template(templates.get("email", DEFAULT_TEMPLATES["email"]), patient, proc, settings, link)
    else:
        tresc = render_template(templates.get("sms", DEFAULT_TEMPLATES["sms"]), patient, proc, settings, link)

    sent_at = now_utc() - timedelta(days=random.randint(0, 25)) if historical else now_utc()

    # Dispatch: SMS via Twilio gateway; EMAIL via Emergent Resend proxy (both mock-fallback).
    if historical:
        status, is_mock, err = "WYSLANO", True, None
    elif channel == "SMS":
        res = send_sms(patient.get("telefon", ""), tresc)
        status, is_mock, err = res["status"], res["mock"], res.get("error")
    else:
        subject = render_template(templates.get("email_temat", DEFAULT_TEMPLATES["email_temat"]),
                                  patient, proc, settings, link)
        html = _email_html(patient, tresc, link, clinic)
        res = await send_email_reminder(patient.get("email", ""), subject, html, settings)
        status, is_mock, err = res["status"], res["mock"], res.get("error")

    # Determine sequence step for this reminder
    if seq_step is None:
        seq_step = 2 if channel == "EMAIL" else 1

    reminder = {
        "pacjent_id": str(patient["_id"]),
        "pacjent_imie": f"{patient.get('imie','')} {patient.get('nazwisko','')}",
        "typ": channel,
        "odbiorca": patient.get("telefon") if channel == "SMS" else patient.get("email"),
        "tresc": tresc,
        "status": status,
        "mock": is_mock,
        "blad": err,
        "krok_sekwencji": seq_step,
        "data_wyslania": iso(sent_at),
        "data_dostarczenia": iso(sent_at + timedelta(seconds=5)) if status == "WYSLANO" else None,
    }
    await db.reminders.insert_one(reminder)
    await db.patients.update_one(
        {"_id": patient["_id"]},
        {"$set": {
            "status_recallu": STATUS_REMINDED,
            "data_ostatniego_przypomnienia": iso(sent_at),
            "sekwencja_krok": seq_step,
            "zaktualizowano": iso(now_utc()),
        }},
    )
    return reminder


async def _create_appointment(patient: dict, when: datetime, historical: bool = False, source: str = "RECALL"):
    created = now_utc() - timedelta(days=random.randint(0, 20)) if historical else now_utc()
    appt = {
        "pacjent_id": str(patient["_id"]),
        "pacjent_imie": f"{patient.get('imie','')} {patient.get('nazwisko','')}",
        "data_wizyty": iso(when),
        "status": "ZAPLANOWANA",
        "zrodlo": source,
        "procedura": patient.get("typ_ostatniej_procedury", ""),
        "utworzono": iso(created),
    }
    await db.appointments.insert_one(appt)
    await db.patients.update_one(
        {"_id": patient["_id"]},
        {"$set": {"status_recallu": STATUS_BOOKED, "zaktualizowano": iso(now_utc())}},
    )
    return appt


async def advance_sequences() -> dict:
    """Advance the multi-channel reminder sequence for patients awaiting a reaction.
    Step flow: DO_PRZYPOMNIENIA -> SMS (step1) -> +3d email (step2) -> +7d SMS (step3, end).
    Booked / rejected patients are skipped (they reacted)."""
    result = {"nowe_sms": 0, "email": 0, "final_sms": 0}
    today = now_utc()

    # Step 1: newly due patients get the initial SMS
    async for p in db.patients.find({"status_recallu": STATUS_DUE, "wykluczony": False}):
        if p.get("zgoda_sms"):
            await _send_reminder(p, channel="SMS", seq_step=1)
            result["nowe_sms"] += 1
        else:
            # no SMS consent: try starting with email if allowed
            if p.get("zgoda_email"):
                await _send_reminder(p, channel="EMAIL", seq_step=2)
                result["email"] += 1

    # Follow-up steps for patients still in PRZYPOMNIANY (no booking/rejection yet)
    async for p in db.patients.find({"status_recallu": STATUS_REMINDED, "wykluczony": False}):
        krok = p.get("sekwencja_krok", 1)
        last = p.get("data_ostatniego_przypomnienia")
        if not last or krok >= 3:
            continue
        try:
            last_dt = datetime.fromisoformat(last)
        except Exception:
            continue
        gap = SEQ_GAP_DAYS.get(krok)
        if gap is None:
            continue
        if (today - last_dt).days < gap:
            continue
        if krok == 1:
            # move to email follow-up
            if p.get("zgoda_email"):
                await _send_reminder(p, channel="EMAIL", seq_step=2)
                result["email"] += 1
            else:
                # skip email, go straight to final SMS
                if p.get("zgoda_sms"):
                    await _send_reminder(p, channel="SMS", seq_step=3)
                    result["final_sms"] += 1
        elif krok == 2:
            # final SMS reminder
            if p.get("zgoda_sms"):
                await _send_reminder(p, channel="SMS", seq_step=3)
                result["final_sms"] += 1
            else:
                await db.patients.update_one({"_id": p["_id"]}, {"$set": {"sekwencja_krok": 3}})
    return result


async def run_daily_recall() -> dict:
    """Full nightly job for the clinic in context: scan, advance sequence, 24h visit reminders."""
    marked = await run_recall_scan()
    seq = await advance_sequences()
    r24 = await send_24h_reminders()
    return {"marked_due": marked, **seq, "przypomnienia_24h": r24}


def render_24h(tpl: str, patient: dict, appt: dict, settings: dict) -> str:
    try:
        when = datetime.fromisoformat(appt["data_wizyty"])
        data_s, godz_s = when.strftime("%d.%m.%Y"), when.strftime("%H:%M")
    except Exception:
        data_s, godz_s = appt.get("data_wizyty", ""), ""
    return (tpl
            .replace("{imie}", patient.get("imie", ""))
            .replace("{nazwisko}", patient.get("nazwisko", ""))
            .replace("{data_wizyty}", data_s)
            .replace("{godzina_wizyty}", godz_s)
            .replace("{nazwa_gabinetu}", settings.get("nazwa_gabinetu", ""))
            .replace("{adres}", settings.get("adres", ""))
            .replace("{telefon_gabinetu}", settings.get("telefon", "")))


async def send_24h_reminders() -> int:
    """SMS to every patient with a planned visit within the next 24-48h window (sent once per visit)."""
    settings = await db.settings.find_one({}) or DEFAULT_SETTINGS
    templates = await db.templates.find_one({}) or DEFAULT_TEMPLATES
    tpl = templates.get("sms_24h") or DEFAULT_TEMPLATES["sms_24h"]
    now = now_utc()
    lo, hi = iso(now), iso(now + timedelta(hours=48))
    sent = 0
    async for a in db.appointments.find({"status": "ZAPLANOWANA", "przypomnienie_24h": {"$ne": True},
                                         "data_wizyty": {"$gte": lo, "$lte": hi}}):
        try:
            p = await db.patients.find_one({"_id": ObjectId(a["pacjent_id"])})
        except Exception:
            p = None
        if not p or not p.get("telefon"):
            continue
        tresc = render_24h(tpl, p, a, settings)
        res = send_sms(p["telefon"], tresc)
        await db.reminders.insert_one({
            "pacjent_id": a["pacjent_id"],
            "pacjent_imie": f"{p.get('imie','')} {p.get('nazwisko','')}",
            "typ": "SMS",
            "rodzaj": "PRZYPOMNIENIE_24H",
            "odbiorca": p["telefon"],
            "tresc": tresc,
            "status": res["status"],
            "mock": res["mock"],
            "blad": res.get("error"),
            "krok_sekwencji": None,
            "data_wyslania": iso(now),
            "data_dostarczenia": iso(now + timedelta(seconds=5)) if res["status"] == "WYSLANO" else None,
        })
        await db.appointments.update_one({"_id": a["_id"]},
                                         {"$set": {"przypomnienie_24h": True, "przypomnienie_24h_data": iso(now)}})
        sent += 1
    return sent


async def run_daily_recall_all_clinics() -> dict:
    """Cron entrypoint: run the daily job for every registered clinic."""
    summary = {}
    async for c in raw_db.clinics.find({}):
        cid = str(c["_id"])
        set_clinic(cid)
        try:
            summary[cid] = await run_daily_recall()
        except Exception as e:
            logging.getLogger(__name__).error("Daily recall failed for clinic %s: %s", cid, e)
            summary[cid] = {"error": str(e)}
    set_clinic(None)
    return summary


# ---------------------------------------------------------------------------
# Routes: dashboard
# ---------------------------------------------------------------------------
@public_router.get("/")
async def root():
    return {"message": "Recall API"}


@api_router.get("/dashboard/stats")
async def dashboard_stats():
    counts = {}
    for st in [STATUS_ACTIVE, STATUS_DUE, STATUS_REMINDED, STATUS_BOOKED, STATUS_REJECTED]:
        counts[st] = await db.patients.count_documents({"status_recallu": st, "wykluczony": False})
    total = await db.patients.count_documents({})

    start = (now_utc() - timedelta(days=29)).date()
    days = {(start + timedelta(days=i)).isoformat(): {"data": (start + timedelta(days=i)).isoformat(),
                                                       "przypomnienia": 0, "zapisy": 0} for i in range(30)}
    async for r in db.reminders.find({}):
        d = (r.get("data_wyslania") or "")[:10]
        if d in days:
            days[d]["przypomnienia"] += 1
    async for a in db.appointments.find({}):
        d = (a.get("utworzono") or "")[:10]
        if d in days:
            days[d]["zapisy"] += 1
    chart = [days[k] for k in sorted(days.keys())]
    return {"counts": counts, "total": total, "chart": chart}


# ---------------------------------------------------------------------------
# Routes: patients
# ---------------------------------------------------------------------------
@api_router.get("/patients")
async def list_patients(status: Optional[str] = None, procedura: Optional[str] = None,
                        search: Optional[str] = None):
    q: dict = {}
    if status and status != "WSZYSCY":
        q["status_recallu"] = status
    if procedura and procedura != "WSZYSTKIE":
        q["typ_ostatniej_procedury"] = procedura
    if search:
        q["$or"] = [
            {"imie": {"$regex": search, "$options": "i"}},
            {"nazwisko": {"$regex": search, "$options": "i"}},
            {"telefon": {"$regex": search, "$options": "i"}},
        ]
    docs = await db.patients.find(q).sort("zaktualizowano", -1).to_list(2000)
    return [clean(d) for d in docs]


@api_router.post("/patients")
async def create_patient(p: PatientCreate):
    doc = Patient(**p.model_dump()).model_dump()
    res = await db.patients.insert_one(doc)
    await run_recall_scan()
    return clean(await db.patients.find_one({"_id": res.inserted_id}))


@api_router.put("/patients/{pid}")
async def update_patient(pid: str, upd: PatientUpdate):
    data = {k: v for k, v in upd.model_dump().items() if v is not None}
    data["zaktualizowano"] = iso(now_utc())
    r = await db.patients.update_one({"_id": ObjectId(pid)}, {"$set": data})
    if r.matched_count == 0:
        raise HTTPException(404, "Pacjent nie znaleziony")
    await run_recall_scan()
    return clean(await db.patients.find_one({"_id": ObjectId(pid)}))


@api_router.delete("/patients/{pid}")
async def delete_patient(pid: str):
    await db.patients.delete_one({"_id": ObjectId(pid)})
    return {"ok": True}


@api_router.post("/patients/{pid}/remind")
async def remind_now(pid: str, channel: str = "SMS"):
    p = await db.patients.find_one({"_id": ObjectId(pid)})
    if not p:
        raise HTTPException(404, "Pacjent nie znaleziony")
    if channel == "SMS" and not p.get("zgoda_sms"):
        raise HTTPException(400, "Brak zgody pacjenta na SMS")
    if channel == "EMAIL" and not p.get("zgoda_email"):
        raise HTTPException(400, "Brak zgody pacjenta na email")
    r = await _send_reminder(p, channel=channel)
    return {"ok": True, "reminder": clean(r)}


@api_router.post("/patients/{pid}/exclude")
async def exclude_patient(pid: str):
    await db.patients.update_one({"_id": ObjectId(pid)},
                                 {"$set": {"wykluczony": True, "status_recallu": STATUS_ACTIVE,
                                           "zaktualizowano": iso(now_utc())}})
    return {"ok": True}


@api_router.post("/patients/{pid}/include")
async def include_patient(pid: str):
    await db.patients.update_one({"_id": ObjectId(pid)},
                                 {"$set": {"wykluczony": False, "zaktualizowano": iso(now_utc())}})
    await run_recall_scan()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Routes: CSV import
# ---------------------------------------------------------------------------
def _validate_row(row: dict) -> List[str]:
    errors = []
    if not row.get("imie") or not row.get("nazwisko"):
        errors.append("Brak imienia lub nazwiska")
    tel = (row.get("telefon") or "").strip()
    if tel and not PHONE_RE.match(tel):
        errors.append("Nieprawidłowy telefon")
    em = (row.get("email") or "").strip()
    if em and not EMAIL_RE.match(em):
        errors.append("Nieprawidłowy email")
    if not tel and not em:
        errors.append("Brak telefonu i emaila")
    return errors


COLUMN_ALIASES = {
    "imie": ["imie", "imię", "first_name", "imie_pacjenta"],
    "nazwisko": ["nazwisko", "last_name", "surname"],
    "telefon": ["telefon", "tel", "phone", "numer", "numer_telefonu"],
    "email": ["email", "e-mail", "mail", "adres_email"],
    "data_ostatniej_wizyty": ["data_ostatniej_wizyty", "ostatnia_wizyta", "data_wizyty", "last_visit"],
    "typ_ostatniej_procedury": ["typ_ostatniej_procedury", "procedura", "typ_procedury", "procedure"],
}


def _map_headers(headers: List[str]) -> dict:
    mapping = {}
    low = {h.strip().lower(): h for h in headers}
    for field, aliases in COLUMN_ALIASES.items():
        for a in aliases:
            if a in low:
                mapping[field] = low[a]
                break
    return mapping


def _normalize_date(val: str) -> str:
    val = (val or "").strip()
    if not val:
        return ""
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(val, fmt).date().isoformat()
        except Exception:
            continue
    return val


@api_router.post("/patients/import/preview")
async def import_preview(file: UploadFile = File(...)):
    content = (await file.read()).decode("utf-8-sig", errors="ignore")
    delim = ";" if content.count(";") > content.count(",") else ","
    reader = csv.DictReader(io.StringIO(content), delimiter=delim)
    headers = reader.fieldnames or []
    mapping = _map_headers(headers)
    rows = []
    valid = 0
    invalid = 0
    for raw in reader:
        row = {field: (raw.get(src, "") or "").strip() for field, src in mapping.items()}
        row["data_ostatniej_wizyty"] = _normalize_date(row.get("data_ostatniej_wizyty", ""))
        errors = _validate_row(row)
        row["_errors"] = errors
        if errors:
            invalid += 1
        else:
            valid += 1
        rows.append(row)
    return {"headers": headers, "mapping": mapping, "rows": rows[:200],
            "total": len(rows), "valid": valid, "invalid": invalid}


class ImportCommit(BaseModel):
    rows: List[dict]


@api_router.post("/patients/import/commit")
async def import_commit(payload: ImportCommit):
    inserted = 0
    for row in payload.rows:
        if row.get("_errors"):
            continue
        doc = Patient(
            imie=row.get("imie", ""),
            nazwisko=row.get("nazwisko", ""),
            telefon=row.get("telefon", ""),
            email=row.get("email", ""),
            data_ostatniej_wizyty=row.get("data_ostatniej_wizyty", ""),
            typ_ostatniej_procedury=row.get("typ_ostatniej_procedury", ""),
            zgoda_sms=bool(row.get("telefon")),
            zgoda_email=bool(row.get("email")),
        ).model_dump()
        await db.patients.insert_one(doc)
        inserted += 1
    marked = await run_recall_scan()
    return {"inserted": inserted, "marked_due": marked}


# ---------------------------------------------------------------------------
# Routes: procedures
# ---------------------------------------------------------------------------
@api_router.get("/procedures")
async def list_procedures():
    docs = await db.procedures.find({}).to_list(200)
    return [clean(d) for d in docs]


@api_router.post("/procedures")
async def create_procedure(p: Procedure):
    res = await db.procedures.insert_one(p.model_dump())
    return clean(await db.procedures.find_one({"_id": res.inserted_id}))


@api_router.put("/procedures/{pid}")
async def update_procedure(pid: str, upd: ProcedureUpdate):
    data = {k: v for k, v in upd.model_dump().items() if v is not None}
    await db.procedures.update_one({"_id": ObjectId(pid)}, {"$set": data})
    await run_recall_scan()
    return clean(await db.procedures.find_one({"_id": ObjectId(pid)}))


@api_router.delete("/procedures/{pid}")
async def delete_procedure(pid: str):
    await db.procedures.delete_one({"_id": ObjectId(pid)})
    return {"ok": True}


# ---------------------------------------------------------------------------
# Routes: templates & settings
# ---------------------------------------------------------------------------
@api_router.get("/templates")
async def get_templates():
    t = await db.templates.find_one({})
    return clean(t) if t else DEFAULT_TEMPLATES


@api_router.put("/templates")
async def update_templates(payload: dict):
    payload.pop("id", None)
    payload.pop("_id", None)
    existing = await db.templates.find_one({})
    if existing:
        await db.templates.update_one({"_id": existing["_id"]}, {"$set": payload})
    else:
        await db.templates.insert_one(payload)
    return clean(await db.templates.find_one({}))


def _mask_settings(s: dict) -> dict:
    s = clean(dict(s))
    key = s.pop("resend_api_key", "") or ""
    s.pop("clinic_id", None)
    s["resend_api_key_ustawiony"] = bool(key.strip())
    s["resend_api_key_podglad"] = f"{key[:6]}…{key[-4:]}" if len(key) > 10 else ""
    return s


@api_router.get("/settings")
async def get_settings():
    s = await db.settings.find_one({})
    return _mask_settings(s if s else DEFAULT_SETTINGS)


@api_router.put("/settings")
async def update_settings(payload: dict):
    payload.pop("id", None)
    payload.pop("_id", None)
    payload.pop("clinic_id", None)
    payload.pop("resend_api_key_ustawiony", None)
    payload.pop("resend_api_key_podglad", None)
    if "resend_api_key" in payload and payload["resend_api_key"] is None:
        payload.pop("resend_api_key")
    if payload.get("email_nadawca") and not EMAIL_RE.match(payload["email_nadawca"].strip()):
        raise HTTPException(400, "Nieprawidłowy adres nadawcy")
    existing = await db.settings.find_one({})
    if existing:
        await db.settings.update_one({"_id": existing["_id"]}, {"$set": payload})
    else:
        await db.settings.insert_one(payload)
    return _mask_settings(await db.settings.find_one({}))


# ---------------------------------------------------------------------------
# Routes: reminders & recall trigger
# ---------------------------------------------------------------------------
@api_router.get("/reminders")
async def list_reminders(typ: Optional[str] = None):
    q = {}
    if typ and typ != "WSZYSTKIE":
        q["typ"] = typ
    docs = await db.reminders.find(q).sort("data_wyslania", -1).to_list(1000)
    return [clean(d) for d in docs]


@api_router.post("/recall/run")
async def recall_run():
    result = await run_daily_recall()
    return result


def _cron_authorized(authorization: Optional[str]) -> bool:
    secret = os.environ.get("WEBHOOK_CRON_SECRET")
    if not secret or not authorization:
        return False
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return False
    return hmac.compare_digest(parts[1], secret)


@public_router.post("/cron/recall-sequence")
async def cron_recall_sequence(background_tasks: BackgroundTasks,
                               authorization: Optional[str] = Header(default=None)):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    if not _cron_authorized(authorization):
        raise HTTPException(status_code=401, detail="Unauthorized")
    background_tasks.add_task(run_daily_recall_all_clinics)
    return {"accepted": True}


@api_router.post("/appointments/send-24h-reminders")
async def trigger_24h_reminders():
    return {"wyslano": await send_24h_reminders()}


@api_router.get("/appointments/upcoming")
async def upcoming_appointments():
    now = iso(now_utc())
    docs = await db.appointments.find({"status": "ZAPLANOWANA", "data_wizyty": {"$gte": now}}).sort("data_wizyty", 1).to_list(500)
    return [clean(d) for d in docs]


# ---------------------------------------------------------------------------
# Routes: ROI
# ---------------------------------------------------------------------------
@api_router.get("/roi")
async def roi_report():
    start = now_utc() - timedelta(days=30)
    start_iso = iso(start)
    reminders = await db.reminders.count_documents({"data_wyslania": {"$gte": start_iso}})
    appts = await db.appointments.find({"utworzono": {"$gte": start_iso}, "zrodlo": {"$in": ["RECALL", "ONLINE"]}}).to_list(2000)
    rejected = await db.patients.count_documents({"status_recallu": STATUS_REJECTED})
    procs = {p["nazwa"]: p for p in await db.procedures.find({}).to_list(100)}
    revenue = 0
    for a in appts:
        proc = procs.get(a.get("procedura"))
        revenue += proc["wartosc"] if proc else 200
    booked = len(appts)
    conv = round((booked / reminders * 100), 1) if reminders else 0.0
    return {
        "przypomnienia": reminders,
        "zapisy": booked,
        "odrzucenia": rejected,
        "szacunkowy_przychod": revenue,
        "konwersja": conv,
    }


_FONTS_READY = False


def _ensure_fonts():
    global _FONTS_READY
    if _FONTS_READY:
        return
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    base = "/usr/share/fonts/truetype/liberation"
    try:
        pdfmetrics.registerFont(TTFont("PL", f"{base}/LiberationSans-Regular.ttf"))
        pdfmetrics.registerFont(TTFont("PL-Bold", f"{base}/LiberationSans-Bold.ttf"))
    except Exception:
        pdfmetrics.registerFont(TTFont("PL", "/usr/share/fonts/truetype/freefont/FreeSans.ttf"))
        pdfmetrics.registerFont(TTFont("PL-Bold", "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"))
    _FONTS_READY = True


@api_router.get("/roi/pdf")
async def roi_pdf():
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    from reportlab.lib.colors import HexColor

    _ensure_fonts()
    roi = await roi_report()
    settings = await db.settings.find_one({}) or DEFAULT_SETTINGS
    okres_do = now_utc().date()
    okres_od = okres_do - timedelta(days=30)

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    green = HexColor("#2D6A4F")
    dark = HexColor("#1C1917")
    muted = HexColor("#57534E")
    accent = HexColor("#D4A373")

    # Header band
    c.setFillColor(green)
    c.rect(0, h - 45 * mm, w, 45 * mm, fill=1, stroke=0)
    c.setFillColor(HexColor("#FFFFFF"))
    c.setFont("PL-Bold", 22)
    c.drawString(20 * mm, h - 22 * mm, "Raport ROI — recall pacjentów")
    c.setFont("PL", 12)
    c.drawString(20 * mm, h - 31 * mm, settings.get("nazwa_gabinetu", ""))
    c.setFont("PL", 10)
    c.drawString(20 * mm, h - 38 * mm, f"Okres: {okres_od.isoformat()} — {okres_do.isoformat()}")

    # Big revenue card
    y = h - 70 * mm
    c.setFillColor(green)
    c.roundRect(20 * mm, y, w - 40 * mm, 30 * mm, 6, fill=1, stroke=0)
    c.setFillColor(HexColor("#FFFFFF"))
    c.setFont("PL", 11)
    c.drawString(28 * mm, y + 20 * mm, "Szacunkowy przychód z odzyskanych wizyt")
    c.setFont("PL-Bold", 28)
    rev = f"{roi['szacunkowy_przychod']:,}".replace(",", " ") + " zł"
    c.drawString(28 * mm, y + 7 * mm, rev)

    # Stat rows
    stats = [
        ("Wysłanych przypomnień", str(roi["przypomnienia"])),
        ("Pacjentów zapisanych na wizytę", str(roi["zapisy"])),
        ("Odrzuceń", str(roi["odrzucenia"])),
        ("Współczynnik konwersji", f"{roi['konwersja']}%"),
    ]
    ry = y - 18 * mm
    for label, val in stats:
        c.setStrokeColor(HexColor("#E5E7EB"))
        c.setLineWidth(0.6)
        c.line(20 * mm, ry - 3 * mm, w - 20 * mm, ry - 3 * mm)
        c.setFillColor(muted)
        c.setFont("PL", 12)
        c.drawString(22 * mm, ry, label)
        c.setFillColor(dark)
        c.setFont("PL-Bold", 14)
        c.drawRightString(w - 22 * mm, ry, val)
        ry -= 14 * mm

    # Footer note
    c.setFillColor(muted)
    c.setFont("PL", 9)
    note = ("Jeden odzyskany pacjent (np. leczenie kanałowe ~1500 zł) często zwraca roczny "
            "koszt subskrypcji. Dane obejmują ostatnie 30 dni.")
    c.drawString(20 * mm, 25 * mm, note)
    c.setFillColor(accent)
    c.setFont("PL-Bold", 9)
    c.drawString(20 * mm, 18 * mm, f"RecallDent · Plan {settings.get('plan','')}")
    c.setFillColor(muted)
    c.setFont("PL", 8)
    c.drawString(20 * mm, 13 * mm, f"Wygenerowano: {now_utc().strftime('%Y-%m-%d %H:%M')} UTC")

    c.showPage()
    c.save()
    buf.seek(0)
    fname = f"raport_roi_{okres_do.isoformat()}.pdf"
    return Response(content=buf.read(), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})


@api_router.get("/sms-status")
async def sms_status():
    settings = await db.settings.find_one({}) or {}
    own = bool((settings.get("resend_api_key") or "").strip() and (settings.get("email_nadawca") or "").strip())
    return {"skonfigurowane": twilio_configured(),
            "tryb": "REALNY" if twilio_configured() else "MOCK",
            "provider": "Twilio",
            "email_skonfigurowane": own or email_configured(),
            "email_tryb": "REALNY" if (own or email_configured()) else "MOCK",
            "email_provider": "Resend",
            "email_wlasna_domena": own,
            "email_nadawca": settings.get("email_nadawca") if own else None}


class TestEmailIn(BaseModel):
    do: str


@api_router.post("/settings/test-email")
async def settings_test_email(payload: TestEmailIn):
    settings = await db.settings.find_one({}) or DEFAULT_SETTINGS
    if not EMAIL_RE.match(payload.do.strip()):
        raise HTTPException(400, "Nieprawidłowy adres email")
    clinic = settings.get("nazwa_gabinetu", "")
    html = _email_html({}, f"To jest testowa wiadomość z systemu RecallDent dla gabinetu {clinic}. "
                       "Jeśli ją widzisz, konfiguracja nadawcy działa poprawnie.", app_base_url() or "#", clinic)
    res = await send_email_reminder(payload.do.strip(), f"Test konfiguracji email — {clinic}", html, settings)
    if res["status"] != "WYSLANO":
        raise HTTPException(400, res.get("error") or "Wysyłka nie powiodła się")
    return {"ok": True, "mock": res["mock"], "provider": res.get("provider")}


SEQ_STEP_LABEL = {
    0: "Nie rozpoczęto",
    1: "Wysłano SMS (krok 1)",
    2: "Wysłano email (krok 2)",
    3: "Wysłano SMS przypominający (krok 3 — koniec)",
}


@api_router.get("/patients/{pid}/timeline")
async def patient_timeline(pid: str):
    p = await db.patients.find_one({"_id": ObjectId(pid)})
    if not p:
        raise HTTPException(404, "Pacjent nie znaleziony")
    reminders = await db.reminders.find({"pacjent_id": pid}).sort("data_wyslania", 1).to_list(200)
    appts = await db.appointments.find({"pacjent_id": pid}).sort("utworzono", 1).to_list(200)

    krok = p.get("sekwencja_krok", 0)
    status = p.get("status_recallu")
    next_step = None
    last = p.get("data_ostatniego_przypomnienia")
    if status == STATUS_REMINDED and krok in SEQ_GAP_DAYS and last:
        try:
            due = datetime.fromisoformat(last) + timedelta(days=SEQ_GAP_DAYS[krok])
            next_typ = "EMAIL" if krok == 1 else "SMS"
            next_step = {"typ": next_typ, "data": iso(due), "krok": krok + 1}
        except Exception:
            next_step = None

    return {
        "pacjent": clean(p),
        "sekwencja_krok": krok,
        "sekwencja_krok_opis": SEQ_STEP_LABEL.get(krok, ""),
        "nastepny_krok": next_step,
        "przypomnienia": [clean(r) for r in reminders],
        "wizyty": [clean(a) for a in appts],
    }


# ---------------------------------------------------------------------------
# Routes: public patient booking
# ---------------------------------------------------------------------------
def generate_slots(settings: dict) -> List[dict]:
    slots = []
    g_od = settings.get("godzina_od", 10)
    g_do = settings.get("godzina_do", 18)
    today = now_utc().date()
    day = today + timedelta(days=1)
    added_days = 0
    while added_days < 7:
        if day.weekday() < 5:
            times = []
            for h in range(g_od, g_do):
                for m in (0, 30):
                    times.append(f"{h:02d}:{m:02d}")
            slots.append({"data": day.isoformat(), "godziny": random.sample(times, min(5, len(times)))})
            added_days += 1
        day += timedelta(days=1)
    for s in slots:
        s["godziny"] = sorted(s["godziny"])
    return slots


async def get_clinic_slots() -> List[dict]:
    """Return clinic-defined upcoming free slots grouped by date, or [] if none set."""
    today = now_utc().date().isoformat()
    docs = await db.slots.find({"data": {"$gte": today}, "zajety": False}).sort([("data", 1), ("godzina", 1)]).to_list(500)
    grouped: dict = {}
    for d in docs:
        grouped.setdefault(d["data"], []).append(d["godzina"])
    return [{"data": k, "godziny": grouped[k]} for k in sorted(grouped.keys())]


class SlotCreate(BaseModel):
    data: str
    godziny: List[str]


@api_router.get("/slots")
async def list_slots():
    today = now_utc().date().isoformat()
    docs = await db.slots.find({"data": {"$gte": today}}).sort([("data", 1), ("godzina", 1)]).to_list(500)
    return [clean(d) for d in docs]


@api_router.post("/slots")
async def create_slots(payload: SlotCreate):
    added = 0
    for g in payload.godziny:
        exists = await db.slots.find_one({"data": payload.data, "godzina": g})
        if exists:
            continue
        await db.slots.insert_one({"data": payload.data, "godzina": g, "zajety": False, "pacjent_id": None})
        added += 1
    return {"added": added}


@api_router.delete("/slots/{sid}")
async def delete_slot(sid: str):
    await db.slots.delete_one({"_id": ObjectId(sid)})
    return {"ok": True}


def _public_settings(s: dict) -> dict:
    s = clean(dict(s))
    for k in ("resend_api_key", "email_reply_to", "clinic_id", "plan"):
        s.pop(k, None)
    return s


async def _public_patient(pid: str) -> dict:
    """Resolve a patient from a public link and bind the tenant context to their clinic."""
    try:
        p = await raw_db.patients.find_one({"_id": ObjectId(pid)})
    except Exception:
        p = None
    if not p:
        raise HTTPException(404, "Nie znaleziono")
    set_clinic(p.get("clinic_id"))
    return p


@public_router.get("/booking/{pid}")
async def booking_info(pid: str):
    p = await _public_patient(pid)
    settings = await db.settings.find_one({}) or DEFAULT_SETTINGS
    procs = {x["nazwa"]: x for x in await db.procedures.find({}).to_list(100)}
    proc = procs.get(p.get("typ_ostatniej_procedury"))
    existing = await db.appointments.find_one({"pacjent_id": pid, "status": "ZAPLANOWANA"})
    clinic_slots = await get_clinic_slots()
    sloty = clinic_slots if clinic_slots else generate_slots(settings)
    return {
        "pacjent": {"imie": p.get("imie"), "nazwisko": p.get("nazwisko")},
        "procedura": p.get("typ_ostatniej_procedury"),
        "interwal": interval_label(proc["interwal_miesiace"]) if proc else "6 miesięcy",
        "status": p.get("status_recallu"),
        "gabinet": _public_settings(settings),
        "sloty": sloty,
        "reczne_terminy": bool(clinic_slots),
        "istniejaca_wizyta": clean(existing) if existing else None,
    }


class BookingConfirm(BaseModel):
    data: str
    godzina: str


@public_router.post("/booking/{pid}/confirm")
async def booking_confirm(pid: str, payload: BookingConfirm):
    p = await _public_patient(pid)
    when = datetime.fromisoformat(f"{payload.data}T{payload.godzina}:00+00:00")
    appt = await _create_appointment(p, when=when, source="ONLINE")
    settings = await db.settings.find_one({}) or DEFAULT_SETTINGS
    # mark clinic-defined slot as taken (if it exists)
    await db.slots.update_one(
        {"data": payload.data, "godzina": payload.godzina},
        {"$set": {"zajety": True, "pacjent_id": pid}},
    )
    confirm_text = (f"Potwierdzenie: Twoja wizyta w {settings.get('nazwa_gabinetu','')} została "
                    f"zarezerwowana na {payload.data} {payload.godzina}. Do zobaczenia!")
    res = send_sms(p.get("telefon", ""), confirm_text)
    await db.reminders.insert_one({
        "pacjent_id": pid,
        "pacjent_imie": f"{p.get('imie','')} {p.get('nazwisko','')}",
        "typ": "SMS",
        "odbiorca": p.get("telefon"),
        "tresc": confirm_text,
        "status": res["status"],
        "mock": res["mock"],
        "blad": res.get("error"),
        "data_wyslania": iso(now_utc()),
        "data_dostarczenia": iso(now_utc()) if res["status"] == "WYSLANO" else None,
    })
    return {"ok": True, "wizyta": clean(appt), "gabinet": _public_settings(settings)}


@public_router.post("/booking/{pid}/reject")
async def booking_reject(pid: str):
    await _public_patient(pid)
    await db.patients.update_one({"_id": ObjectId(pid)},
                                 {"$set": {"status_recallu": STATUS_REJECTED, "zaktualizowano": iso(now_utc())}})
    return {"ok": True}


# ---------------------------------------------------------------------------
# Admin: reset demo
# ---------------------------------------------------------------------------
@api_router.post("/admin/reset-demo")
async def reset_demo():
    for c in ["patients", "procedures", "settings", "templates", "reminders", "appointments", "slots"]:
        await db[c].delete_many({})
    await seed_if_empty(demo=True)
    return {"ok": True}


@api_router.post("/admin/load-demo")
async def load_demo():
    await seed_if_empty(demo=True)
    return {"ok": True}


async def _seed_new_clinic(cid: str, demo: bool, nazwa: str):
    token = set_clinic(cid)
    try:
        await seed_if_empty(demo=demo, nazwa=nazwa)
    finally:
        set_clinic(None)


async def _migrate_orphans(cid: str):
    """Assign pre-auth documents (no clinic_id) to the admin clinic."""
    for c in ["patients", "procedures", "settings", "templates", "reminders", "appointments", "slots"]:
        await raw_db[c].update_many({"clinic_id": {"$exists": False}}, {"$set": {"clinic_id": cid}})
    set_clinic(cid)
    try:
        await seed_if_empty(demo=True)
    finally:
        set_clinic(None)


auth.init(raw_db, _seed_new_clinic)
app.include_router(auth.router)
app.include_router(public_router)
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@app.on_event("startup")
async def startup():
    await auth.ensure_indexes()
    await auth.seed_admin(_migrate_orphans)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()

from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import io
import csv
import re
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
db = client[os.environ['DB_NAME']]

app = FastAPI()
api_router = APIRouter(prefix="/api")


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
}

DEFAULT_TEMPLATES = {
    "sms": "Pacjent {imie}, minęło {interwal} od ostatniej wizyty ({procedura}). Zarezerwuj wizytę kontrolną: {link_do_zapisu} — {nazwa_gabinetu}",
    "email_temat": "Czas na wizytę kontrolną w {nazwa_gabinetu}",
    "email": "Dzień dobry {imie} {nazwisko},\n\nminęło {interwal} od Twojej ostatniej wizyty ({procedura}). Zapraszamy na wizytę kontrolną.\n\nZarezerwuj termin online: {link_do_zapisu}\n\nPozdrawiamy,\n{nazwa_gabinetu}",
}

IMIONA_M = ["Jan", "Piotr", "Andrzej", "Tomasz", "Marcin", "Michał", "Krzysztof", "Paweł", "Adam", "Jakub"]
IMIONA_K = ["Anna", "Maria", "Katarzyna", "Agnieszka", "Barbara", "Ewa", "Magdalena", "Joanna", "Zofia", "Julia"]
NAZWISKA = ["Nowak", "Kowalski", "Wiśniewski", "Wójcik", "Kowalczyk", "Kamiński", "Lewandowski", "Zieliński",
            "Szymański", "Woźniak", "Dąbrowski", "Kozłowski", "Jankowski", "Mazur", "Kwiatkowski"]


async def seed_if_empty():
    if await db.procedures.count_documents({}) == 0:
        await db.procedures.insert_many([dict(p) for p in DEFAULT_PROCEDURES])
    if await db.settings.count_documents({}) == 0:
        await db.settings.insert_one(dict(DEFAULT_SETTINGS))
    if await db.templates.count_documents({}) == 0:
        await db.templates.insert_one(dict(DEFAULT_TEMPLATES))
    if await db.patients.count_documents({}) == 0:
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


async def _send_reminder(patient: dict, channel: str = "SMS", historical: bool = False):
    settings = await db.settings.find_one({}) or DEFAULT_SETTINGS
    templates = await db.templates.find_one({}) or DEFAULT_TEMPLATES
    procs = {p["nazwa"]: p for p in await db.procedures.find({}).to_list(100)}
    proc = procs.get(patient.get("typ_ostatniej_procedury"))
    link = f"/zapis/{str(patient['_id'])}"
    if channel == "EMAIL":
        tresc = render_template(templates.get("email", DEFAULT_TEMPLATES["email"]), patient, proc, settings, link)
    else:
        tresc = render_template(templates.get("sms", DEFAULT_TEMPLATES["sms"]), patient, proc, settings, link)

    sent_at = now_utc() - timedelta(days=random.randint(0, 25)) if historical else now_utc()

    reminder = {
        "pacjent_id": str(patient["_id"]),
        "pacjent_imie": f"{patient.get('imie','')} {patient.get('nazwisko','')}",
        "typ": channel,
        "odbiorca": patient.get("telefon") if channel == "SMS" else patient.get("email"),
        "tresc": tresc,
        "status": "WYSLANO",
        "mock": True,
        "data_wyslania": iso(sent_at),
        "data_dostarczenia": iso(sent_at + timedelta(seconds=5)),
    }
    await db.reminders.insert_one(reminder)
    await db.patients.update_one(
        {"_id": patient["_id"]},
        {"$set": {
            "status_recallu": STATUS_REMINDED,
            "data_ostatniego_przypomnienia": iso(sent_at),
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


# ---------------------------------------------------------------------------
# Routes: dashboard
# ---------------------------------------------------------------------------
@api_router.get("/")
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


@api_router.get("/settings")
async def get_settings():
    s = await db.settings.find_one({})
    return clean(s) if s else DEFAULT_SETTINGS


@api_router.put("/settings")
async def update_settings(payload: dict):
    payload.pop("id", None)
    payload.pop("_id", None)
    existing = await db.settings.find_one({})
    if existing:
        await db.settings.update_one({"_id": existing["_id"]}, {"$set": payload})
    else:
        await db.settings.insert_one(payload)
    return clean(await db.settings.find_one({}))


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
    marked = await run_recall_scan()
    return {"marked_due": marked}


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


@api_router.get("/booking/{pid}")
async def booking_info(pid: str):
    try:
        p = await db.patients.find_one({"_id": ObjectId(pid)})
    except Exception:
        raise HTTPException(404, "Nie znaleziono")
    if not p:
        raise HTTPException(404, "Nie znaleziono")
    settings = await db.settings.find_one({}) or DEFAULT_SETTINGS
    procs = {x["nazwa"]: x for x in await db.procedures.find({}).to_list(100)}
    proc = procs.get(p.get("typ_ostatniej_procedury"))
    existing = await db.appointments.find_one({"pacjent_id": pid, "status": "ZAPLANOWANA"})
    return {
        "pacjent": {"imie": p.get("imie"), "nazwisko": p.get("nazwisko")},
        "procedura": p.get("typ_ostatniej_procedury"),
        "interwal": interval_label(proc["interwal_miesiace"]) if proc else "6 miesięcy",
        "status": p.get("status_recallu"),
        "gabinet": clean(settings),
        "sloty": generate_slots(settings),
        "istniejaca_wizyta": clean(existing) if existing else None,
    }


class BookingConfirm(BaseModel):
    data: str
    godzina: str


@api_router.post("/booking/{pid}/confirm")
async def booking_confirm(pid: str, payload: BookingConfirm):
    p = await db.patients.find_one({"_id": ObjectId(pid)})
    if not p:
        raise HTTPException(404, "Nie znaleziono")
    when = datetime.fromisoformat(f"{payload.data}T{payload.godzina}:00+00:00")
    appt = await _create_appointment(p, when=when, source="ONLINE")
    settings = await db.settings.find_one({}) or DEFAULT_SETTINGS
    await db.reminders.insert_one({
        "pacjent_id": pid,
        "pacjent_imie": f"{p.get('imie','')} {p.get('nazwisko','')}",
        "typ": "SMS",
        "odbiorca": p.get("telefon"),
        "tresc": f"Potwierdzenie: Twoja wizyta w {settings.get('nazwa_gabinetu','')} została zarezerwowana na {payload.data} {payload.godzina}. Do zobaczenia!",
        "status": "WYSLANO",
        "mock": True,
        "data_wyslania": iso(now_utc()),
        "data_dostarczenia": iso(now_utc()),
    })
    return {"ok": True, "wizyta": clean(appt), "gabinet": clean(settings)}


@api_router.post("/booking/{pid}/reject")
async def booking_reject(pid: str):
    p = await db.patients.find_one({"_id": ObjectId(pid)})
    if not p:
        raise HTTPException(404, "Nie znaleziono")
    await db.patients.update_one({"_id": ObjectId(pid)},
                                 {"$set": {"status_recallu": STATUS_REJECTED, "zaktualizowano": iso(now_utc())}})
    return {"ok": True}


# ---------------------------------------------------------------------------
# Admin: reset demo
# ---------------------------------------------------------------------------
@api_router.post("/admin/reset-demo")
async def reset_demo():
    for c in ["patients", "procedures", "settings", "templates", "reminders", "appointments"]:
        await db[c].delete_many({})
    await seed_if_empty()
    return {"ok": True}


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
    await seed_if_empty()


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()

import os
import re
import bcrypt
import jwt
from datetime import datetime, timezone, timedelta
from typing import Optional, Callable, Awaitable
from bson import ObjectId
from fastapi import APIRouter, HTTPException, Request, Response, Depends
from pydantic import BaseModel

from tenant import set_clinic

JWT_ALGORITHM = "HS256"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_raw_db = None
_on_register: Optional[Callable[[str, bool], Awaitable[None]]] = None


def init(raw_db, on_register):
    global _raw_db, _on_register
    _raw_db = raw_db
    _on_register = on_register


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def _secret() -> str:
    return os.environ["JWT_SECRET"]


def create_access_token(user_id: str, clinic_id: str, email: str) -> str:
    payload = {"sub": user_id, "cid": clinic_id, "email": email, "type": "access",
               "exp": datetime.now(timezone.utc) + timedelta(hours=12)}
    return jwt.encode(payload, _secret(), algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    payload = {"sub": user_id, "type": "refresh", "exp": datetime.now(timezone.utc) + timedelta(days=30)}
    return jwt.encode(payload, _secret(), algorithm=JWT_ALGORITHM)


def _set_cookies(response: Response, access: str, refresh: str):
    response.set_cookie("access_token", access, httponly=True, secure=True, samesite="none", max_age=43200, path="/")
    response.set_cookie("refresh_token", refresh, httponly=True, secure=True, samesite="none", max_age=2592000, path="/")


def _public_user(u: dict) -> dict:
    return {"id": str(u["_id"]), "email": u["email"], "imie": u.get("imie", ""),
            "clinic_id": u["clinic_id"], "rola": u.get("rola", "owner")}


def _extract_token(request: Request) -> Optional[str]:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return request.cookies.get("access_token")


async def get_current_user(request: Request) -> dict:
    token = _extract_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Wymagane logowanie")
    try:
        payload = jwt.decode(token, _secret(), algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Sesja wygasła")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Nieprawidłowy token")
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Nieprawidłowy typ tokenu")
    user = await _raw_db.users.find_one({"_id": ObjectId(payload["sub"])})
    if not user:
        raise HTTPException(status_code=401, detail="Użytkownik nie istnieje")
    set_clinic(user["clinic_id"])
    return user


async def require_clinic(user: dict = Depends(get_current_user)) -> str:
    return user["clinic_id"]


# ---------------------------------------------------------------------------
# Brute force protection: 5 failures / 15 min per ip:email
# ---------------------------------------------------------------------------
MAX_ATTEMPTS = 5
LOCK_MINUTES = 15


async def _check_lock(identifier: str):
    rec = await _raw_db.login_attempts.find_one({"identifier": identifier})
    if rec and rec.get("count", 0) >= MAX_ATTEMPTS:
        locked_until = rec.get("locked_until")
        if locked_until and locked_until > datetime.now(timezone.utc):
            raise HTTPException(status_code=429, detail="Zbyt wiele prób. Spróbuj ponownie za 15 minut.")
        await _raw_db.login_attempts.delete_one({"identifier": identifier})


async def _record_failure(identifier: str):
    rec = await _raw_db.login_attempts.find_one({"identifier": identifier})
    count = (rec or {}).get("count", 0) + 1
    upd = {"count": count, "updated_at": datetime.now(timezone.utc)}
    if count >= MAX_ATTEMPTS:
        upd["locked_until"] = datetime.now(timezone.utc) + timedelta(minutes=LOCK_MINUTES)
    await _raw_db.login_attempts.update_one({"identifier": identifier}, {"$set": upd}, upsert=True)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
router = APIRouter(prefix="/api/auth")


class RegisterIn(BaseModel):
    email: str
    password: str
    nazwa_gabinetu: str
    imie: str = ""
    dane_demo: bool = False


class LoginIn(BaseModel):
    email: str
    password: str


async def create_clinic_with_owner(email: str, password: str, nazwa_gabinetu: str, imie: str = "",
                                   demo: bool = False) -> dict:
    now = datetime.now(timezone.utc)
    clinic = await _raw_db.clinics.insert_one({"nazwa": nazwa_gabinetu, "utworzono": now.isoformat()})
    cid = str(clinic.inserted_id)
    user_doc = {"email": email, "password_hash": hash_password(password), "imie": imie,
                "clinic_id": cid, "rola": "owner", "utworzono": now.isoformat()}
    res = await _raw_db.users.insert_one(user_doc)
    user_doc["_id"] = res.inserted_id
    if _on_register:
        await _on_register(cid, demo, nazwa_gabinetu)
    return user_doc


@router.post("/register")
async def register(payload: RegisterIn, response: Response):
    email = payload.email.strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(400, "Nieprawidłowy adres email")
    if len(payload.password) < 8:
        raise HTTPException(400, "Hasło musi mieć co najmniej 8 znaków")
    if not payload.nazwa_gabinetu.strip():
        raise HTTPException(400, "Podaj nazwę gabinetu")
    if await _raw_db.users.find_one({"email": email}):
        raise HTTPException(409, "Konto z tym adresem email już istnieje")
    user = await create_clinic_with_owner(email, payload.password, payload.nazwa_gabinetu.strip(),
                                          payload.imie.strip(), payload.dane_demo)
    access = create_access_token(str(user["_id"]), user["clinic_id"], email)
    _set_cookies(response, access, create_refresh_token(str(user["_id"])))
    return {"token": access, "user": _public_user(user)}


@router.post("/login")
async def login(payload: LoginIn, request: Request, response: Response):
    email = payload.email.strip().lower()
    ip = request.client.host if request.client else "unknown"
    identifier = f"{ip}:{email}"
    await _check_lock(identifier)
    user = await _raw_db.users.find_one({"email": email})
    if not user or not verify_password(payload.password, user["password_hash"]):
        await _record_failure(identifier)
        raise HTTPException(401, "Nieprawidłowy email lub hasło")
    await _raw_db.login_attempts.delete_one({"identifier": identifier})
    access = create_access_token(str(user["_id"]), user["clinic_id"], email)
    _set_cookies(response, access, create_refresh_token(str(user["_id"])))
    return {"token": access, "user": _public_user(user)}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return {"ok": True}


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return _public_user(user)


@router.post("/refresh")
async def refresh(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(401, "Brak tokenu odświeżania")
    try:
        payload = jwt.decode(token, _secret(), algorithms=[JWT_ALGORITHM])
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Nieprawidłowy token")
    if payload.get("type") != "refresh":
        raise HTTPException(401, "Nieprawidłowy typ tokenu")
    user = await _raw_db.users.find_one({"_id": ObjectId(payload["sub"])})
    if not user:
        raise HTTPException(401, "Użytkownik nie istnieje")
    access = create_access_token(str(user["_id"]), user["clinic_id"], user["email"])
    _set_cookies(response, access, create_refresh_token(str(user["_id"])))
    return {"token": access, "user": _public_user(user)}


async def ensure_indexes():
    await _raw_db.users.create_index("email", unique=True)
    await _raw_db.login_attempts.create_index("identifier")


async def seed_admin(migrate_orphans: Callable[[str], Awaitable[None]]):
    email = os.environ["ADMIN_EMAIL"].lower()
    password = os.environ["ADMIN_PASSWORD"]
    existing = await _raw_db.users.find_one({"email": email})
    if existing is None:
        user = await create_clinic_with_owner(email, password, os.environ.get("EMAIL_FROM_NAME", "Gabinet"),
                                              "Administrator", demo=False)
        await migrate_orphans(user["clinic_id"])
    elif not verify_password(password, existing["password_hash"]):
        await _raw_db.users.update_one({"_id": existing["_id"]}, {"$set": {"password_hash": hash_password(password)}})

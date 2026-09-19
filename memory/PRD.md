# PRD — RecallDent: System automatycznego recallu pacjentów dla gabinetów stomatologicznych

## Original Problem Statement
MVP SaaS dla gabinetów stomatologicznych (1–3 foteli, Polska), który automatycznie identyfikuje pacjentów wymagających wizyty kontrolnej i wysyła spersonalizowane przypomnienia SMS/email z linkiem do zapisu — bez angażowania recepcji. Model subskrypcyjny 79–129 zł/mies.

## User Choices
- Uwierzytelnianie: JWT email+hasło, konto właściciela per gabinet, multi-tenant (clinic_id przez ContextVar TenantDB)
- SMS: Twilio (integracja gotowa, tryb MOCK — brak poprawnych kluczy: podano SK... zamiast Account SID AC... i brak numeru nadawcy)
- Email: Resend zarządzany przez Emergent (domyślnie) LUB własny klucz Resend + adres nadawcy per gabinet (Ustawienia gabinetu)
- Cron: codziennie 09:00 Europe/Warsaw
- Sekwencja: Dzień 0 SMS → +3 dni email → +7 dni SMS → koniec
- Design: wybór agenta (paleta zieleń szałwiowa, Outfit + DM Sans)

## Architecture
- Frontend: React 19 + React Router + Tailwind + shadcn/ui + Recharts + Framer Motion
- Backend: FastAPI + Motor (MongoDB), trasy z prefiksem `/api`
- Integracje: Twilio (SMS, mock-fallback), Emergent Resend (email), reportlab (PDF)
- DB kolekcje: patients, procedures, settings, templates, reminders, appointments, slots
- Cron: `.emergent/crons.yml` → `POST /api/cron/recall-sequence` (bearer WEBHOOK_CRON_SECRET)

## Core Requirements (static)
- Import CSV + ręczne dodawanie pacjentów z walidacją
- Silnik recallu: skan interwałów per procedura + sekwencja wielokanałowa
- Wysyłka SMS (Twilio) / email (Resend) z szablonami i polami dynamicznymi
- Publiczny link zapisu online + ręcznie definiowane terminy przez gabinet
- Panel: dashboard, lista pacjentów z osią czasu sekwencji, raport ROI + eksport PDF
- Ustawienia: interwały, szablony, godziny wysyłki, dane gabinetu, terminy

## Implemented
### 2026-06-19 (MVP)
- ✅ Backend API (dashboard, patients CRUD, remind, exclude, CSV import, procedures, templates, settings, reminders, recall, ROI, public booking, reset-demo)
- ✅ Silnik recallu + panel gabinetu (8 ekranów) + mobilny widok pacjenta
- ✅ Dane demo auto-seed (32 pacjentów, 5 procedur)
### 2026-06-19 (iter. 2)
- ✅ Eksport PDF raportu ROI (reportlab, Liberation Sans, polskie znaki)
- ✅ Integracja Twilio SMS z fallbackiem MOCK
- ✅ Nocny cron 09:00 + endpoint zabezpieczony bearer tokenem
- ✅ Sekwencja wielokanałowa SMS → email → SMS z uwzględnieniem zgód
### 2026-06-19 (iter. 3)
- ✅ Realny email przez Resend (Emergent-managed), graceful fallback
- ✅ Oś czasu sekwencji na karcie pacjenta (GET /patients/{id}/timeline)
- ✅ Panel ręcznie definiowanych terminów (/terminy) widocznych w linku zapisu
- ✅ Testy: 28/28 backend + frontend 100%

### 2026-06-20 (iter. 4)
- ✅ Logowanie/rejestracja gabinetu (JWT, bcrypt, brute-force lock 5/15min), izolacja danych per gabinet (`tenant.py`, `auth.py`)
- ✅ Migracja starych danych demo do gabinetu admina; cron iteruje po wszystkich gabinetach
- ✅ Własna domena nadawcy email per gabinet: klucz Resend (maskowany), adres nadawcy, reply-to, test-email, instrukcja weryfikacji DNS
- ✅ SMS 24h przed wizytą (szablon `sms_24h`, cron + ręczny trigger `/appointments/send-24h-reminders`, badge w Wiadomościach)
- ✅ Testy: 25/25 backend + frontend flows (iteration_4)

### 2026-06-20 (iter. 5)
- ✅ Konta pracowników: role owner/recepcja, zaproszenia emailem (7 dni), akceptacja `/zaproszenie/{token}`, strona „Zespół gabinetu”, owner-only endpointy (settings, templates, procedures, delete patient, reset-demo) → 403, banner read-only w UI
- ✅ Potwierdzenie wizyty TAK/NIE: webhook `/api/sms/inbound` (Twilio format), publiczna strona `/potwierdz/{aid}`, symulacja w panelu, strona „Nadchodzące wizyty” ze statusem; NIE → wizyta ODWOLANA, pacjent wraca do recallu
- ✅ Reset hasła: `/nie-pamietam-hasla` → email (Emergent Resend) z linkiem `/reset-hasla/{token}` (1h, jednorazowy)
- ✅ Testy: 29/29 backend (po poprawce migracji szablonu sms_24h) + frontend flows (iteration_5)

## Backlog / Remaining
- P0: Realny SMS — użytkownik odrzucił Twilio (~20$) i SMSAPI (49 zł start); SMS pozostaje MOCK do czasu wyboru bramki
- P2: Walidacja slotów po stronie API (format HH:MM, data >= dziś), sprawdzanie istnienia slotu przy reczne_terminy
- P2: Refactor server.py (1151 linii) na routery/serwisy
- P2: Integracja API z systemami gabinetowymi (SmartDental, Dentidesk, Medfile)
- P2: Zarządzanie zgodami RODO + umowa powierzenia

## Next Tasks
- Bramka SMS (gdy użytkownik zdecyduje)
- Email 24h przed wizytą jako darmowa alternatywa dla SMS
- Walidacja slotów po stronie API

# PRD — RecallDent: System automatycznego recallu pacjentów dla gabinetów stomatologicznych

## Original Problem Statement
MVP SaaS dla gabinetów stomatologicznych (1–3 foteli, Polska), który automatycznie identyfikuje pacjentów wymagających wizyty kontrolnej i wysyła spersonalizowane przypomnienia SMS/email z linkiem do zapisu — bez angażowania recepcji. Model subskrypcyjny 79–129 zł/mies.

## User Choices
- Uwierzytelnianie: BRAK (tryb demo, panel bez logowania)
- Wysyłka SMS/Email: SYMULACJA (MOCK) — wiadomości zapisywane w bazie, widoczne w panelu
- Raport ROI: podgląd na ekranie (bez eksportu PDF)
- Dane startowe: przykładowe dane demonstracyjne (32 pacjentów, 5 procedur)
- Design: wybór agenta (paleta "Organic & Earthy" — zieleń szałwiowa, Outfit + DM Sans)

## Architecture
- Frontend: React 19 + React Router + Tailwind + shadcn/ui + Recharts + Framer Motion
- Backend: FastAPI + Motor (MongoDB), wszystkie trasy z prefiksem `/api`
- DB kolekcje: patients, procedures, settings, templates, reminders, appointments

## User Personas
- Właściciel/menedżer gabinetu: przegląda dashboard, ROI, zarządza pacjentami i szablonami
- Recepcja: import CSV, wysyłka przypomnień, obsługa listy pacjentów
- Pacjent: otwiera publiczny link `/zapis/{id}`, rezerwuje termin lub rezygnuje

## Core Requirements (static)
- Import CSV + ręczne dodawanie pacjentów z walidacją telefonu/email
- Silnik recallu: skan interwałów per procedura, statusy AKTYWNY → DO_PRZYPOMNIENIA → PRZYPOMNIANY → ZAPISANY/ODRZUCONY
- Wysyłka przypomnień SMS/email (MOCK) z szablonami i polami dynamicznymi
- Publiczny link zapisu online (landing → wybór terminu → potwierdzenie/odrzucenie + .ics)
- Panel: dashboard z kafelkami i wykresem 30-dniowym, lista pacjentów z filtrami, raport ROI
- Ustawienia: interwały procedur, szablony, godziny wysyłki, dane gabinetu

## Implemented (2026-06-19)
- ✅ Pełny backend API (dashboard, patients CRUD, remind, exclude/include, CSV import preview+commit, procedures, templates, settings, reminders, recall/run, ROI, public booking, reset-demo)
- ✅ Silnik recallu z automatycznym skanem + ręczny trigger "Uruchom skanowanie"
- ✅ Panel gabinetu: Dashboard, Lista pacjentów, Import, Ustawienia recallu, Szablony, Wysłane wiadomości, Raport ROI, Ustawienia gabinetu
- ✅ Mobilny widok pacjenta z pełnym flow zapisu/odrzucenia
- ✅ Dane demonstracyjne auto-seed (32 pacjentów, 5 procedur)
- ✅ Testy: 13/13 backend pass, frontend 100% pass

## Backlog / Remaining
- P1: Eksport raportu ROI do PDF
- P1: Realna bramka SMS (SMSAPI/Twilio) + email (Resend) zamiast MOCK
- P1: Uwierzytelnianie i multi-tenant (wiele gabinetów)
- P2: Automatyczny nocny cron dla skanu recallu (obecnie skan przy starcie + ręczny przycisk)
- P2: Sekwencja wielokanałowa z opóźnieniami (SMS → 3 dni → email → 7 dni → SMS)
- P2: Integracja API z systemami gabinetowymi (SmartDental, Dentidesk, Medfile)
- P2: Zarządzanie zgodami RODO i umowa powierzenia

## Next Tasks
- Eksport PDF raportu ROI
- Podpięcie realnej wysyłki SMS/email
- Cron nocny dla silnika recallu

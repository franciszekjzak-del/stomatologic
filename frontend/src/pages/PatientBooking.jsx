import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { motion, AnimatePresence } from "framer-motion";
import { CalendarDays, MapPin, Phone, CheckCircle2, Clock, Stethoscope, CalendarPlus, Heart } from "lucide-react";

const HERO = "https://images.pexels.com/photos/5355860/pexels-photo-5355860.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940";

const dayLabel = (iso) => {
  const d = new Date(iso);
  const days = ["niedz.", "pon.", "wt.", "śr.", "czw.", "pt.", "sob."];
  const months = ["sty", "lut", "mar", "kwi", "maj", "cze", "lip", "sie", "wrz", "paź", "lis", "gru"];
  return `${days[d.getDay()]} ${d.getDate()} ${months[d.getMonth()]}`;
};

export default function PatientBooking() {
  const { pid } = useParams();
  const [info, setInfo] = useState(null);
  const [step, setStep] = useState("landing");
  const [selDay, setSelDay] = useState(null);
  const [selTime, setSelTime] = useState(null);
  const [confirmed, setConfirmed] = useState(null);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    api.get(`/booking/${pid}`)
      .then((r) => {
        setInfo(r.data);
        setSelDay(r.data.sloty?.[0]?.data);
        if (r.data.istniejaca_wizyta) { setConfirmed(r.data.istniejaca_wizyta); setStep("done"); }
        if (r.data.status === "ODRZUCONY") setStep("rejected");
      })
      .catch(() => setNotFound(true));
  }, [pid]);

  const confirm = async () => {
    const r = await api.post(`/booking/${pid}/confirm`, { data: selDay, godzina: selTime });
    setConfirmed(r.data.wizyta);
    setStep("done");
  };

  const reject = async () => {
    await api.post(`/booking/${pid}/reject`);
    setStep("rejected");
  };

  const addToCalendar = () => {
    if (!confirmed) return;
    const start = new Date(confirmed.data_wizyty);
    const end = new Date(start.getTime() + 30 * 60000);
    const fmt = (d) => d.toISOString().replace(/[-:]/g, "").split(".")[0] + "Z";
    const ics = `BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\nDTSTART:${fmt(start)}\nDTEND:${fmt(end)}\nSUMMARY:Wizyta kontrolna - ${info.gabinet.nazwa_gabinetu}\nLOCATION:${info.gabinet.adres || ""}\nEND:VEVENT\nEND:VCALENDAR`;
    const blob = new Blob([ics], { type: "text/calendar" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "wizyta.ics"; a.click();
    URL.revokeObjectURL(url);
  };

  if (notFound) return <div className="min-h-screen flex items-center justify-center text-muted-foreground">Nie znaleziono zaproszenia.</div>;
  if (!info) return <div className="min-h-screen flex items-center justify-center text-muted-foreground">Ładowanie...</div>;

  const g = info.gabinet;
  const daySlots = info.sloty?.find((s) => s.data === selDay);

  return (
    <div className="min-h-screen bg-gradient-to-b from-secondary/60 to-background flex justify-center" data-testid="booking-page">
      <div className="w-full max-w-md bg-card min-h-screen shadow-xl">
        {/* Header */}
        <div className="px-6 pt-6 pb-4 flex items-center gap-2.5 border-b border-border">
          <div className="h-9 w-9 rounded-xl bg-primary flex items-center justify-center overflow-hidden">
            {g.logo_url ? <img src={g.logo_url} alt="logo" className="h-full w-full object-cover" /> : <Stethoscope className="h-5 w-5 text-primary-foreground" />}
          </div>
          <div>
            <div className="font-head font-bold text-sm leading-tight">{g.nazwa_gabinetu}</div>
            <div className="text-[11px] text-muted-foreground flex items-center gap-1"><MapPin className="h-3 w-3" /> {g.adres}</div>
          </div>
        </div>

        <AnimatePresence mode="wait">
          {step === "landing" && (
            <motion.div key="landing" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}>
              <img src={HERO} alt="Gabinet" className="w-full h-56 object-cover" />
              <div className="p-6">
                <h1 className="font-head text-2xl font-bold leading-snug">
                  {info.pacjent.imie}, czas na wizytę kontrolną 🦷
                </h1>
                <p className="text-muted-foreground mt-3 leading-relaxed">
                  Minęło <b>{info.interwal}</b> od Twojej ostatniej wizyty
                  {info.procedura ? <> (<b>{info.procedura}</b>)</> : null}. Zadbaj o swój uśmiech — zarezerwuj dogodny termin w kilka sekund.
                </p>
                <Button data-testid="start-booking-btn" onClick={() => setStep("slots")} className="w-full mt-6 h-12 text-base gap-2 hover:-translate-y-0.5 transition-transform">
                  <CalendarDays className="h-5 w-5" /> Zapisz się na wizytę
                </Button>
                <button data-testid="reject-btn" onClick={reject} className="w-full mt-3 text-sm text-muted-foreground hover:text-foreground py-2 transition-colors">
                  Nie interesuje mnie wizyta kontrolna
                </button>
              </div>
            </motion.div>
          )}

          {step === "slots" && (
            <motion.div key="slots" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }} className="p-6">
              <h2 className="font-head text-xl font-bold mb-1">Wybierz termin</h2>
              <p className="text-sm text-muted-foreground mb-5">Dostępne wolne terminy w gabinecie</p>

              <div className="flex gap-2 overflow-x-auto pb-3 -mx-1 px-1">
                {info.sloty.map((s) => (
                  <button
                    key={s.data}
                    data-testid={`day-${s.data}`}
                    onClick={() => { setSelDay(s.data); setSelTime(null); }}
                    className={`shrink-0 px-3 py-2.5 rounded-xl border text-sm transition-colors ${
                      selDay === s.data ? "bg-primary text-primary-foreground border-primary" : "bg-card border-border hover:border-primary/50"
                    }`}
                  >
                    {dayLabel(s.data)}
                  </button>
                ))}
              </div>

              <div className="grid grid-cols-3 gap-2.5 mt-4">
                {daySlots?.godziny.map((t) => (
                  <button
                    key={t}
                    data-testid={`time-${t}`}
                    onClick={() => setSelTime(t)}
                    className={`py-3 rounded-xl border text-sm font-medium flex items-center justify-center gap-1.5 transition-colors ${
                      selTime === t ? "bg-primary text-primary-foreground border-primary" : "bg-card border-border hover:border-primary/50"
                    }`}
                  >
                    <Clock className="h-3.5 w-3.5" /> {t}
                  </button>
                ))}
              </div>

              <Button data-testid="confirm-booking-btn" onClick={confirm} disabled={!selTime} className="w-full mt-6 h-12 text-base">
                Potwierdź {selTime && `— ${dayLabel(selDay)}, ${selTime}`}
              </Button>
              <button onClick={() => setStep("landing")} className="w-full mt-3 text-sm text-muted-foreground py-2">Wróć</button>
            </motion.div>
          )}

          {step === "done" && confirmed && (
            <motion.div key="done" initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="p-6 text-center">
              <div className="mx-auto h-16 w-16 rounded-full bg-emerald-100 flex items-center justify-center mb-5 mt-6">
                <CheckCircle2 className="h-9 w-9 text-emerald-600" />
              </div>
              <h2 className="font-head text-2xl font-bold">Wizyta zarezerwowana!</h2>
              <div className="mt-4 p-4 rounded-2xl bg-secondary/60 inline-block">
                <div className="font-head text-lg font-semibold" data-testid="confirmed-date">
                  {dayLabel(confirmed.data_wizyty.slice(0, 10))}, {confirmed.data_wizyty.slice(11, 16)}
                </div>
              </div>
              <p className="text-muted-foreground mt-4 leading-relaxed">
                Otrzymasz SMS z przypomnieniem 24h przed wizytą. Do zobaczenia w {g.nazwa_gabinetu}!
              </p>
              <Button data-testid="add-calendar-btn" onClick={addToCalendar} variant="outline" className="w-full mt-6 gap-2">
                <CalendarPlus className="h-4 w-4" /> Dodaj do kalendarza
              </Button>
              {g.telefon && (
                <div className="text-sm text-muted-foreground mt-4 flex items-center justify-center gap-1.5">
                  <Phone className="h-3.5 w-3.5" /> {g.telefon}
                </div>
              )}
            </motion.div>
          )}

          {step === "rejected" && (
            <motion.div key="rejected" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="p-6 text-center">
              <div className="mx-auto h-16 w-16 rounded-full bg-secondary flex items-center justify-center mb-5 mt-10">
                <Heart className="h-8 w-8 text-muted-foreground" />
              </div>
              <h2 className="font-head text-xl font-bold">Dziękujemy za informację</h2>
              <p className="text-muted-foreground mt-3 leading-relaxed">
                Nie będziemy więcej przypominać o wizytach kontrolnych. W razie potrzeby zapraszamy w dowolnym momencie.
              </p>
              {g.telefon && (
                <div className="text-sm text-muted-foreground mt-6 flex items-center justify-center gap-1.5">
                  <Phone className="h-3.5 w-3.5" /> {g.telefon}
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

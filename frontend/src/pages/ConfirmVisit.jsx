import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api, apiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { CalendarDays, MapPin, Phone, CheckCircle2, XCircle, Stethoscope } from "lucide-react";

const fmt = (iso) => {
  const d = new Date(iso);
  return d.toLocaleString("pl-PL", { weekday: "long", day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" });
};

export default function ConfirmVisit() {
  const { aid } = useParams();
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get(`/appointments/${aid}/public`).then((r) => setData(r.data)).catch((e) => setErr(apiError(e, "Nie znaleziono wizyty")));
  }, [aid]);

  const respond = async (odpowiedz) => {
    setBusy(true);
    try {
      const r = await api.post(`/appointments/${aid}/respond`, { odpowiedz });
      setData({ ...data, wizyta: { ...data.wizyta, potwierdzona: r.data.potwierdzona, status: r.data.status } });
    } catch (e) { setErr(apiError(e)); } finally { setBusy(false); }
  };

  if (err) return <div className="min-h-screen flex items-center justify-center text-muted-foreground p-6" data-testid="confirm-error">{err}</div>;
  if (!data) return null;
  const { wizyta: w, gabinet: g } = data;
  const answered = w.potwierdzona === true || w.status === "ODWOLANA";

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4" data-testid="confirm-visit-page">
      <div className="w-full max-w-md bg-card border border-border rounded-2xl overflow-hidden">
        <div className="bg-primary text-primary-foreground p-6">
          <div className="flex items-center gap-2 mb-4 text-sm opacity-90"><Stethoscope className="h-4 w-4" /> {g.nazwa_gabinetu}</div>
          <h1 className="font-head text-2xl font-bold">Cześć {w.pacjent_imie.split(" ")[0]}!</h1>
          <p className="text-sm opacity-90 mt-1">Przypominamy o Twojej wizycie</p>
        </div>
        <div className="p-6 space-y-4">
          <div className="flex items-start gap-3 text-sm"><CalendarDays className="h-5 w-5 text-primary shrink-0" /><div><div className="font-medium capitalize" data-testid="confirm-visit-date">{fmt(w.data_wizyty)}</div><div className="text-muted-foreground">{w.procedura}</div></div></div>
          {g.adres && <div className="flex items-start gap-3 text-sm"><MapPin className="h-5 w-5 text-primary shrink-0" /><span>{g.adres}</span></div>}
          {g.telefon && <div className="flex items-start gap-3 text-sm"><Phone className="h-5 w-5 text-primary shrink-0" /><a href={`tel:${g.telefon}`} className="underline">{g.telefon}</a></div>}

          {answered ? (
            w.potwierdzona ? (
              <div data-testid="confirm-result-yes" className="rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 p-4 flex gap-3 text-sm">
                <CheckCircle2 className="h-5 w-5 shrink-0" /> Dziękujemy! Wizyta została potwierdzona. Do zobaczenia!
              </div>
            ) : (
              <div data-testid="confirm-result-no" className="rounded-xl bg-rose-50 border border-rose-200 text-rose-800 p-4 flex gap-3 text-sm">
                <XCircle className="h-5 w-5 shrink-0" /> Wizyta została odwołana. Gabinet skontaktuje się z Tobą w sprawie nowego terminu.
              </div>
            )
          ) : (
            <div className="grid grid-cols-2 gap-3 pt-2">
              <Button data-testid="confirm-yes-btn" disabled={busy} onClick={() => respond("TAK")} className="h-12 gap-2"><CheckCircle2 className="h-4 w-4" /> Potwierdzam</Button>
              <Button data-testid="confirm-no-btn" disabled={busy} onClick={() => respond("NIE")} variant="outline" className="h-12 gap-2 text-rose-700 border-rose-200 hover:bg-rose-50"><XCircle className="h-4 w-4" /> Odwołuję</Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

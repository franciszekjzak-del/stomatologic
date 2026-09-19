import { useEffect, useState } from "react";
import { api, apiError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { PageHeader } from "@/components/Shared";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { CalendarCheck, CheckCircle2, XCircle, HelpCircle, MessageSquareReply, Link2 } from "lucide-react";
import { toast } from "sonner";

const fmt = (iso) => new Date(iso).toLocaleString("pl-PL", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });

const Status = ({ a }) => {
  if (a.status === "ODWOLANA") return <Badge data-testid={`appt-status-${a.id}`} className="bg-rose-100 text-rose-700 hover:bg-rose-100 gap-1"><XCircle className="h-3 w-3" /> Odwołana ({a.potwierdzenie_zrodlo})</Badge>;
  if (a.potwierdzona) return <Badge data-testid={`appt-status-${a.id}`} className="bg-emerald-100 text-emerald-700 hover:bg-emerald-100 gap-1"><CheckCircle2 className="h-3 w-3" /> Potwierdzona ({a.potwierdzenie_zrodlo})</Badge>;
  if (a.przypomnienie_24h) return <Badge data-testid={`appt-status-${a.id}`} className="bg-amber-100 text-amber-700 hover:bg-amber-100 gap-1"><HelpCircle className="h-3 w-3" /> Czeka na odpowiedź</Badge>;
  return <Badge data-testid={`appt-status-${a.id}`} variant="secondary" className="gap-1">Zaplanowana</Badge>;
};

export default function Appointments() {
  const [list, setList] = useState([]);
  const { user } = useAuth();
  const load = () => api.get("/appointments/upcoming").then((r) => setList(r.data));
  useEffect(() => { load(); }, []);

  const simulate = async (a, odp) => {
    try {
      await api.post(`/appointments/${a.id}/simulate-reply`, { odpowiedz: odp });
      toast.success(`Zasymulowano odpowiedź „${odp}” od ${a.pacjent_imie}`);
      load();
    } catch (e) { toast.error(apiError(e)); }
  };

  const copy = (a) => { navigator.clipboard?.writeText(a.link_potwierdzenia); toast.success("Skopiowano link potwierdzenia"); };

  const confirmed = list.filter((a) => a.potwierdzona).length;
  const cancelled = list.filter((a) => a.status === "ODWOLANA").length;

  return (
    <div data-testid="appointments-page">
      <PageHeader title="Nadchodzące wizyty" subtitle="Status potwierdzeń z SMS 24h (odpowiedź TAK/NIE lub link). Odwołanie wraca pacjenta do kolejki recallu." />
      <div className="grid sm:grid-cols-3 gap-3 mb-6">
        <Card className="p-4 shadow-none"><div className="text-xs text-muted-foreground">Wizyt</div><div className="font-head text-2xl font-bold" data-testid="appt-total">{list.length}</div></Card>
        <Card className="p-4 shadow-none"><div className="text-xs text-muted-foreground">Potwierdzonych</div><div className="font-head text-2xl font-bold text-emerald-700" data-testid="appt-confirmed">{confirmed}</div></Card>
        <Card className="p-4 shadow-none"><div className="text-xs text-muted-foreground">Odwołanych</div><div className="font-head text-2xl font-bold text-rose-700" data-testid="appt-cancelled">{cancelled}</div></Card>
      </div>
      <div className="space-y-3">
        {list.map((a) => (
          <Card key={a.id} data-testid={`appointment-${a.id}`} className="p-4 shadow-none flex flex-wrap items-center gap-4">
            <div className="h-10 w-10 rounded-xl bg-primary/10 text-primary flex items-center justify-center shrink-0"><CalendarCheck className="h-5 w-5" /></div>
            <div className="flex-1 min-w-[200px]">
              <div className="font-medium text-sm">{a.pacjent_imie} <span className="text-muted-foreground font-normal">· {a.telefon}</span></div>
              <div className="text-sm text-muted-foreground">{fmt(a.data_wizyty)} · {a.procedura} · {a.zrodlo}</div>
            </div>
            <Status a={a} />
            <div className="flex items-center gap-1.5">
              <Button size="sm" variant="ghost" data-testid={`copy-link-${a.id}`} onClick={() => copy(a)} title="Kopiuj link potwierdzenia"><Link2 className="h-4 w-4" /></Button>
              {a.status !== "ODWOLANA" && !a.potwierdzona && (
                <>
                  <Button size="sm" variant="outline" data-testid={`simulate-yes-${a.id}`} onClick={() => simulate(a, "TAK")} className="gap-1.5 text-xs"><MessageSquareReply className="h-3.5 w-3.5" /> Symuluj „TAK”</Button>
                  <Button size="sm" variant="outline" data-testid={`simulate-no-${a.id}`} onClick={() => simulate(a, "NIE")} className="gap-1.5 text-xs text-rose-700">Symuluj „NIE”</Button>
                </>
              )}
            </div>
          </Card>
        ))}
        {list.length === 0 && <div className="text-center py-16 text-muted-foreground">Brak nadchodzących wizyt</div>}
      </div>
      <p className="text-xs text-muted-foreground mt-6">
        Odpowiedzi SMS trafiają na webhook <code className="font-mono">POST /api/sms/inbound</code> (format Twilio: From, Body). W trybie MOCK użyj przycisków „Symuluj” lub linku z SMS. {user?.rola === "owner" ? "" : ""}
      </p>
    </div>
  );
}

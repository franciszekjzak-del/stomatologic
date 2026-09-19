import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/Shared";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Calendar } from "@/components/ui/calendar";
import { Badge } from "@/components/ui/badge";
import { Plus, Trash2, CalendarDays, Clock, X } from "lucide-react";
import { toast } from "sonner";

const ALL_TIMES = [];
for (let h = 8; h <= 19; h++) {
  ALL_TIMES.push(`${String(h).padStart(2, "0")}:00`);
  ALL_TIMES.push(`${String(h).padStart(2, "0")}:30`);
}

const toISO = (d) => {
  const off = d.getTimezoneOffset();
  return new Date(d.getTime() - off * 60000).toISOString().slice(0, 10);
};

const fmtDate = (iso) => {
  const d = new Date(iso);
  const days = ["niedz.", "pon.", "wt.", "śr.", "czw.", "pt.", "sob."];
  const months = ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia", "września", "października", "listopada", "grudnia"];
  return `${days[d.getDay()]}, ${d.getDate()} ${months[d.getMonth()]}`;
};

export default function SlotsPage() {
  const [slots, setSlots] = useState([]);
  const [selDate, setSelDate] = useState(new Date());
  const [picked, setPicked] = useState([]);

  const load = () => api.get("/slots").then((r) => setSlots(r.data));
  useEffect(() => { load(); }, []);

  const togglePick = (t) => setPicked((p) => (p.includes(t) ? p.filter((x) => x !== t) : [...p, t]));

  const addSlots = async () => {
    if (!selDate || picked.length === 0) { toast.error("Wybierz datę i przynajmniej jedną godzinę"); return; }
    const r = await api.post("/slots", { data: toISO(selDate), godziny: picked });
    toast.success(`Dodano ${r.data.added} terminów`);
    setPicked([]);
    load();
  };

  const removeSlot = async (id) => {
    await api.delete(`/slots/${id}`);
    load();
  };

  // group slots by date
  const grouped = slots.reduce((acc, s) => {
    (acc[s.data] = acc[s.data] || []).push(s);
    return acc;
  }, {});
  const dates = Object.keys(grouped).sort();

  // times already defined for the selected date
  const selISO = selDate ? toISO(selDate) : null;
  const existingForSel = new Set((grouped[selISO] || []).map((s) => s.godzina));

  return (
    <div data-testid="slots-page">
      <PageHeader
        title="Dostępne terminy"
        subtitle="Ustaw wolne terminy, które pacjent zobaczy w linku do zapisu online. Jeśli nie dodasz żadnych, system pokaże propozycje automatyczne."
      />

      <div className="grid lg:grid-cols-2 gap-4">
        <Card className="shadow-none p-5">
          <div className="flex items-center gap-2 mb-4">
            <CalendarDays className="h-4 w-4 text-primary" />
            <h3 className="font-head font-semibold">Dodaj terminy</h3>
          </div>
          <div className="flex flex-col sm:flex-row gap-5">
            <div className="shrink-0">
              <Label className="text-xs mb-2 block">Wybierz dzień</Label>
              <div className="rounded-xl border border-border p-2 inline-block">
                <Calendar
                  mode="single"
                  selected={selDate}
                  onSelect={(d) => { setSelDate(d); setPicked([]); }}
                  disabled={(d) => d < new Date(new Date().setHours(0, 0, 0, 0))}
                  data-testid="slot-calendar"
                />
              </div>
            </div>
            <div className="flex-1 min-w-0">
              <Label className="text-xs mb-2 block">Godziny {selDate && `— ${fmtDate(toISO(selDate))}`}</Label>
              <div className="grid grid-cols-3 gap-2 max-h-64 overflow-y-auto pr-1">
                {ALL_TIMES.map((t) => {
                  const already = existingForSel.has(t);
                  const active = picked.includes(t);
                  return (
                    <button
                      key={t}
                      data-testid={`pick-time-${t}`}
                      disabled={already}
                      onClick={() => togglePick(t)}
                      className={`py-2 rounded-lg border text-sm transition-colors ${
                        already ? "bg-secondary text-muted-foreground border-border cursor-not-allowed opacity-60"
                          : active ? "bg-primary text-primary-foreground border-primary"
                          : "bg-card border-border hover:border-primary/50"
                      }`}
                    >
                      {t}{already && " ✓"}
                    </button>
                  );
                })}
              </div>
              <Button data-testid="add-slots-btn" onClick={addSlots} disabled={picked.length === 0} className="w-full mt-4 gap-2">
                <Plus className="h-4 w-4" /> Dodaj {picked.length > 0 ? `${picked.length} terminów` : "terminy"}
              </Button>
            </div>
          </div>
        </Card>

        <Card className="shadow-none p-5">
          <div className="flex items-center gap-2 mb-4">
            <Clock className="h-4 w-4 text-primary" />
            <h3 className="font-head font-semibold">Nadchodzące terminy ({slots.length})</h3>
          </div>
          {dates.length === 0 && (
            <div className="text-center py-12 text-muted-foreground text-sm" data-testid="no-slots">
              Brak zdefiniowanych terminów. Pacjenci zobaczą propozycje automatyczne.
            </div>
          )}
          <div className="space-y-4 max-h-[460px] overflow-y-auto">
            {dates.map((d) => (
              <div key={d} data-testid={`slot-day-${d}`}>
                <div className="text-sm font-medium mb-2">{fmtDate(d)}</div>
                <div className="flex flex-wrap gap-2">
                  {grouped[d].sort((a, b) => a.godzina.localeCompare(b.godzina)).map((s) => (
                    <Badge
                      key={s.id}
                      variant="outline"
                      className={`gap-1.5 py-1.5 pl-3 pr-2 ${s.zajety ? "bg-emerald-50 text-emerald-700 border-emerald-200" : ""}`}
                    >
                      {s.godzina}
                      {s.zajety ? (
                        <span className="text-[10px]">zajęte</span>
                      ) : (
                        <button data-testid={`del-slot-${s.id}`} onClick={() => removeSlot(s.id)} className="hover:text-destructive">
                          <X className="h-3.5 w-3.5" />
                        </button>
                      )}
                    </Badge>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}

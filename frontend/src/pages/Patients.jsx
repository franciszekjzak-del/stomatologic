import { useEffect, useState, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import { api, STATUS_META } from "@/lib/api";
import { PageHeader, StatusBadge } from "@/components/Shared";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { MoreHorizontal, Send, Mail, UserX, Pencil, Plus, Search, ExternalLink, History, Smartphone, CheckCheck, Clock3 } from "lucide-react";
import { toast } from "sonner";

const STATUS_OPTS = ["WSZYSCY", ...Object.keys(STATUS_META)];
const emptyForm = {
  imie: "", nazwisko: "", telefon: "", email: "",
  data_ostatniej_wizyty: "", typ_ostatniej_procedury: "", zgoda_sms: true, zgoda_email: true,
};

export default function Patients() {
  const [params, setParams] = useSearchParams();
  const [patients, setPatients] = useState([]);
  const [procedures, setProcedures] = useState([]);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState(params.get("status") || "WSZYSCY");
  const [proc, setProc] = useState("WSZYSTKIE");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [editId, setEditId] = useState(null);
  const [timeline, setTimeline] = useState(null);
  const [timelineOpen, setTimelineOpen] = useState(false);

  const load = useCallback(() => {
    api.get("/patients", { params: { status, procedura: proc, search: search || undefined } })
      .then((r) => setPatients(r.data));
  }, [status, proc, search]);

  useEffect(() => { api.get("/procedures").then((r) => setProcedures(r.data)); }, []);
  useEffect(() => {
    const t = setTimeout(load, 250);
    return () => clearTimeout(t);
  }, [load]);

  useEffect(() => {
    const p = params.get("status");
    if (p) setStatus(p);
  }, [params]);

  const setStatusFilter = (v) => {
    setStatus(v);
    if (v === "WSZYSCY") setParams({}); else setParams({ status: v });
  };

  const remind = async (id, channel) => {
    try {
      await api.post(`/patients/${id}/remind`, null, { params: { channel } });
      toast.success(`Wysłano przypomnienie ${channel} (symulacja)`);
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Błąd wysyłki");
    }
  };

  const exclude = async (id) => {
    await api.post(`/patients/${id}/exclude`);
    toast.success("Pacjent wykluczony z recallu");
    load();
  };

  const openEdit = (p) => {
    setEditId(p.id);
    setForm({
      imie: p.imie, nazwisko: p.nazwisko, telefon: p.telefon, email: p.email,
      data_ostatniej_wizyty: (p.data_ostatniej_wizyty || "").slice(0, 10),
      typ_ostatniej_procedury: p.typ_ostatniej_procedury,
      zgoda_sms: p.zgoda_sms, zgoda_email: p.zgoda_email,
    });
    setDialogOpen(true);
  };

  const openAdd = () => { setEditId(null); setForm(emptyForm); setDialogOpen(true); };

  const save = async () => {
    if (!form.imie || !form.nazwisko) { toast.error("Podaj imię i nazwisko"); return; }
    try {
      if (editId) await api.put(`/patients/${editId}`, form);
      else await api.post("/patients", form);
      toast.success(editId ? "Zapisano zmiany" : "Dodano pacjenta");
      setDialogOpen(false);
      load();
    } catch { toast.error("Błąd zapisu"); }
  };

  const openBooking = (id) => window.open(`/zapis/${id}`, "_blank");

  const openTimeline = async (id) => {
    setTimeline(null);
    setTimelineOpen(true);
    const r = await api.get(`/patients/${id}/timeline`);
    setTimeline(r.data);
  };

  const fmtDT = (s) => (s ? s.slice(0, 16).replace("T", " ") : "—");

  return (
    <div data-testid="patients-page">
      <PageHeader
        title="Lista pacjentów"
        subtitle={`${patients.length} pacjentów`}
        action={
          <Button data-testid="add-patient-btn" onClick={openAdd} className="gap-2">
            <Plus className="h-4 w-4" /> Dodaj pacjenta
          </Button>
        }
      />

      <Card className="p-4 mb-4 shadow-none">
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              data-testid="patient-search"
              placeholder="Szukaj po imieniu, nazwisku, telefonie..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9"
            />
          </div>
          <Select value={status} onValueChange={setStatusFilter}>
            <SelectTrigger data-testid="filter-status" className="w-full sm:w-52"><SelectValue /></SelectTrigger>
            <SelectContent>
              {STATUS_OPTS.map((s) => (
                <SelectItem key={s} value={s}>{s === "WSZYSCY" ? "Wszystkie statusy" : STATUS_META[s].label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={proc} onValueChange={setProc}>
            <SelectTrigger data-testid="filter-procedure" className="w-full sm:w-52"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="WSZYSTKIE">Wszystkie procedury</SelectItem>
              {procedures.map((p) => <SelectItem key={p.id} value={p.nazwa}>{p.nazwa}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
      </Card>

      <Card className="shadow-none overflow-hidden">
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow className="bg-secondary/50">
                <TableHead>Pacjent</TableHead>
                <TableHead>Kontakt</TableHead>
                <TableHead>Ostatnia wizyta</TableHead>
                <TableHead>Procedura</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Ostatnie przypomn.</TableHead>
                <TableHead className="text-right">Akcje</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {patients.map((p) => (
                <TableRow key={p.id} data-testid={`patient-row-${p.id}`} className="hover:bg-secondary/40">
                  <TableCell className="font-medium">
                    {p.imie} {p.nazwisko}
                    {p.wykluczony && <span className="ml-2 text-[10px] text-muted-foreground">(wykluczony)</span>}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    <div>{p.telefon}</div>
                    <div className="text-xs">{p.email}</div>
                  </TableCell>
                  <TableCell className="text-sm">{(p.data_ostatniej_wizyty || "").slice(0, 10) || "—"}</TableCell>
                  <TableCell className="text-sm">{p.typ_ostatniej_procedury || "—"}</TableCell>
                  <TableCell><StatusBadge status={p.status_recallu} /></TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {p.data_ostatniego_przypomnienia ? p.data_ostatniego_przypomnienia.slice(0, 10) : "—"}
                  </TableCell>
                  <TableCell className="text-right">
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button data-testid={`patient-actions-${p.id}`} variant="ghost" size="icon" className="h-8 w-8">
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem data-testid={`remind-sms-${p.id}`} onClick={() => remind(p.id, "SMS")}>
                          <Send className="h-4 w-4 mr-2" /> Przypomnij SMS
                        </DropdownMenuItem>
                        <DropdownMenuItem data-testid={`remind-email-${p.id}`} onClick={() => remind(p.id, "EMAIL")}>
                          <Mail className="h-4 w-4 mr-2" /> Przypomnij email
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => openBooking(p.id)}>
                          <ExternalLink className="h-4 w-4 mr-2" /> Otwórz link zapisu
                        </DropdownMenuItem>
                        <DropdownMenuItem data-testid={`timeline-${p.id}`} onClick={() => openTimeline(p.id)}>
                          <History className="h-4 w-4 mr-2" /> Oś czasu sekwencji
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => openEdit(p)}>
                          <Pencil className="h-4 w-4 mr-2" /> Edytuj dane
                        </DropdownMenuItem>
                        <DropdownMenuItem data-testid={`exclude-${p.id}`} onClick={() => exclude(p.id)} className="text-destructive">
                          <UserX className="h-4 w-4 mr-2" /> Wyklucz z recallu
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              ))}
              {patients.length === 0 && (
                <TableRow><TableCell colSpan={7} className="text-center py-10 text-muted-foreground">Brak pacjentów</TableCell></TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      </Card>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader><DialogTitle className="font-head">{editId ? "Edytuj pacjenta" : "Dodaj pacjenta"}</DialogTitle></DialogHeader>
          <div className="grid grid-cols-2 gap-4">
            <div><Label>Imię</Label><Input data-testid="form-imie" value={form.imie} onChange={(e) => setForm({ ...form, imie: e.target.value })} /></div>
            <div><Label>Nazwisko</Label><Input data-testid="form-nazwisko" value={form.nazwisko} onChange={(e) => setForm({ ...form, nazwisko: e.target.value })} /></div>
            <div><Label>Telefon</Label><Input data-testid="form-telefon" value={form.telefon} onChange={(e) => setForm({ ...form, telefon: e.target.value })} /></div>
            <div><Label>Email</Label><Input data-testid="form-email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></div>
            <div><Label>Ostatnia wizyta</Label><Input data-testid="form-data" type="date" value={form.data_ostatniej_wizyty} onChange={(e) => setForm({ ...form, data_ostatniej_wizyty: e.target.value })} /></div>
            <div>
              <Label>Procedura</Label>
              <Select value={form.typ_ostatniej_procedury} onValueChange={(v) => setForm({ ...form, typ_ostatniej_procedury: v })}>
                <SelectTrigger data-testid="form-procedura"><SelectValue placeholder="Wybierz" /></SelectTrigger>
                <SelectContent>{procedures.map((p) => <SelectItem key={p.id} value={p.nazwa}>{p.nazwa}</SelectItem>)}</SelectContent>
              </Select>
            </div>
          </div>
          <div className="flex gap-6 pt-2">
            <div className="flex items-center gap-2">
              <Switch data-testid="form-zgoda-sms" checked={form.zgoda_sms} onCheckedChange={(v) => setForm({ ...form, zgoda_sms: v })} />
              <Label className="cursor-pointer">Zgoda SMS</Label>
            </div>
            <div className="flex items-center gap-2">
              <Switch data-testid="form-zgoda-email" checked={form.zgoda_email} onCheckedChange={(v) => setForm({ ...form, zgoda_email: v })} />
              <Label className="cursor-pointer">Zgoda email</Label>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Anuluj</Button>
            <Button data-testid="save-patient-btn" onClick={save}>Zapisz</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={timelineOpen} onOpenChange={setTimelineOpen}>
        <DialogContent className="max-w-lg" data-testid="timeline-dialog">
          <DialogHeader>
            <DialogTitle className="font-head">Oś czasu sekwencji przypomnień</DialogTitle>
          </DialogHeader>
          {!timeline ? (
            <div className="py-8 text-center text-muted-foreground text-sm">Ładowanie...</div>
          ) : (
            <div>
              <div className="flex items-center justify-between mb-4">
                <div>
                  <div className="font-medium">{timeline.pacjent.imie} {timeline.pacjent.nazwisko}</div>
                  <div className="text-sm text-muted-foreground">{timeline.sekwencja_krok_opis}</div>
                </div>
                <StatusBadge status={timeline.pacjent.status_recallu} />
              </div>

              {/* Step progress */}
              <div className="flex items-center gap-1.5 mb-5">
                {[1, 2, 3].map((s) => (
                  <div key={s} className="flex-1">
                    <div className={`h-1.5 rounded-full ${timeline.sekwencja_krok >= s ? "bg-primary" : "bg-secondary"}`} />
                    <div className="text-[10px] text-muted-foreground mt-1 text-center">
                      {s === 1 ? "SMS" : s === 2 ? "Email +3d" : "SMS +7d"}
                    </div>
                  </div>
                ))}
              </div>

              {timeline.nastepny_krok && (
                <div data-testid="next-step" className="flex items-center gap-2 text-sm p-3 rounded-lg bg-amber-50 text-amber-800 border border-amber-200 mb-4">
                  <Clock3 className="h-4 w-4 shrink-0" />
                  Następny krok: <b>{timeline.nastepny_krok.typ}</b> zaplanowany na {fmtDT(timeline.nastepny_krok.data)}
                </div>
              )}

              <div className="space-y-3 max-h-72 overflow-y-auto">
                {timeline.przypomnienia.length === 0 && (
                  <div className="text-sm text-muted-foreground text-center py-6">Brak wysłanych przypomnień</div>
                )}
                {timeline.przypomnienia.map((r) => (
                  <div key={r.id} className="flex gap-3">
                    <div className={`h-8 w-8 rounded-lg flex items-center justify-center shrink-0 ${r.typ === "SMS" ? "bg-sky-50 text-sky-600" : "bg-violet-50 text-violet-600"}`}>
                      {r.typ === "SMS" ? <Smartphone className="h-4 w-4" /> : <Mail className="h-4 w-4" />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm font-medium">{r.typ}</span>
                        {r.krok_sekwencji && <span className="text-[10px] px-1.5 py-0.5 rounded bg-secondary">krok {r.krok_sekwencji}</span>}
                        {r.mock && <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-700">MOCK</span>}
                        <span className={`text-[10px] flex items-center gap-1 ${r.status === "WYSLANO" ? "text-emerald-600" : "text-rose-600"}`}>
                          <CheckCheck className="h-3 w-3" /> {r.status}
                        </span>
                      </div>
                      <div className="text-xs text-muted-foreground">{fmtDT(r.data_wyslania)}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

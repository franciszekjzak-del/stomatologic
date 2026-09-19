import { useEffect, useState } from "react";
import { api, zl } from "@/lib/api";
import { PageHeader } from "@/components/Shared";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Plus, Save, Trash2, Clock } from "lucide-react";
import { toast } from "sonner";

export default function RecallSettings() {
  const [procs, setProcs] = useState([]);
  const [newName, setNewName] = useState("");

  const load = () => api.get("/procedures").then((r) => setProcs(r.data));
  useEffect(() => { load(); }, []);

  const update = (id, patch) => setProcs((ps) => ps.map((p) => (p.id === id ? { ...p, ...patch } : p)));

  const saveOne = async (p) => {
    await api.put(`/procedures/${p.id}`, {
      interwal_miesiace: Number(p.interwal_miesiace),
      wartosc: Number(p.wartosc),
      aktywna: p.aktywna,
    });
    toast.success(`Zapisano: ${p.nazwa}`);
  };

  const addProc = async () => {
    if (!newName.trim()) return;
    await api.post("/procedures", { nazwa: newName, interwal_miesiace: 6, wartosc: 200, aktywna: true });
    setNewName("");
    toast.success("Dodano procedurę");
    load();
  };

  const remove = async (id) => {
    await api.delete(`/procedures/${id}`);
    toast.success("Usunięto procedurę");
    load();
  };

  return (
    <div data-testid="recall-settings-page">
      <PageHeader title="Ustawienia recallu" subtitle="Zdefiniuj interwał przypomnień i szacunkową wartość dla każdej procedury" />

      <Card className="shadow-none divide-y divide-border">
        {procs.map((p) => (
          <div key={p.id} data-testid={`procedure-${p.id}`} className="p-5 flex flex-col md:flex-row md:items-center gap-4">
            <div className="flex items-center gap-3 flex-1 min-w-0">
              <div className="h-10 w-10 rounded-xl bg-secondary flex items-center justify-center shrink-0">
                <Clock className="h-5 w-5 text-primary" />
              </div>
              <div className="font-medium truncate">{p.nazwa}</div>
            </div>
            <div className="flex items-end gap-4 flex-wrap">
              <div>
                <label className="text-xs text-muted-foreground block mb-1">Interwał (miesiące)</label>
                <Input data-testid={`interval-${p.id}`} type="number" min="1" className="w-28"
                  value={p.interwal_miesiace} onChange={(e) => update(p.id, { interwal_miesiace: e.target.value })} />
              </div>
              <div>
                <label className="text-xs text-muted-foreground block mb-1">Wartość wizyty (zł)</label>
                <Input data-testid={`value-${p.id}`} type="number" min="0" className="w-32"
                  value={p.wartosc} onChange={(e) => update(p.id, { wartosc: e.target.value })} />
              </div>
              <div className="flex items-center gap-2 pb-2">
                <Switch data-testid={`active-${p.id}`} checked={p.aktywna} onCheckedChange={(v) => update(p.id, { aktywna: v })} />
                <span className="text-sm text-muted-foreground">{p.aktywna ? "Aktywna" : "Wyłączona"}</span>
              </div>
              <Button data-testid={`save-proc-${p.id}`} size="sm" onClick={() => saveOne(p)} className="gap-1.5">
                <Save className="h-4 w-4" /> Zapisz
              </Button>
              <Button variant="ghost" size="icon" onClick={() => remove(p.id)} className="text-destructive">
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          </div>
        ))}
      </Card>

      <Card className="shadow-none p-5 mt-4 flex gap-3 items-end">
        <div className="flex-1">
          <label className="text-xs text-muted-foreground block mb-1">Nazwa nowej procedury</label>
          <Input data-testid="new-proc-name" placeholder="np. Implant" value={newName} onChange={(e) => setNewName(e.target.value)} />
        </div>
        <Button data-testid="add-proc-btn" onClick={addProc} className="gap-1.5"><Plus className="h-4 w-4" /> Dodaj</Button>
      </Card>
    </div>
  );
}

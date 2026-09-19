import { useEffect, useState } from "react";
import { api, apiError } from "@/lib/api";
import { PageHeader } from "@/components/Shared";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { UserPlus, Trash2, Mail, Crown, Users, Copy, X } from "lucide-react";
import { toast } from "sonner";

export default function Team() {
  const [data, setData] = useState({ uzytkownicy: [], zaproszenia: [] });
  const [form, setForm] = useState({ email: "", imie: "" });
  const [busy, setBusy] = useState(false);
  const [lastLink, setLastLink] = useState("");

  const load = () => api.get("/auth/users").then((r) => setData(r.data));
  useEffect(() => { load(); }, []);

  const invite = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const r = await api.post("/auth/invite", form);
      setLastLink(r.data.link);
      toast.success(r.data.email_status === "WYSLANO" ? `Zaproszenie wysłane na ${form.email}` : "Zaproszenie utworzone — email nie został dostarczony, skopiuj link poniżej");
      setForm({ email: "", imie: "" });
      load();
    } catch (err) { toast.error(apiError(err)); } finally { setBusy(false); }
  };

  const removeUser = async (u) => {
    if (!window.confirm(`Usunąć konto ${u.email}?`)) return;
    await api.delete(`/auth/users/${u.id}`);
    toast.success("Konto usunięte");
    load();
  };

  const cancelInvite = async (i) => {
    await api.delete(`/auth/invite/${i.id}`);
    toast.success("Zaproszenie anulowane");
    load();
  };

  return (
    <div data-testid="team-page">
      <PageHeader title="Zespół gabinetu" subtitle="Pracownicy recepcji widzą pacjentów, wysyłają przypomnienia i zarządzają terminami, ale nie zmieniają ustawień, szablonów ani nie usuwają pacjentów." />

      <div className="grid lg:grid-cols-3 gap-4">
        <Card className="p-6 shadow-none lg:col-span-1">
          <div className="flex items-center gap-2 mb-4"><UserPlus className="h-4 w-4 text-primary" /><h3 className="font-head font-semibold">Zaproś pracownika</h3></div>
          <form onSubmit={invite} className="space-y-3" data-testid="invite-form">
            <div><Label>Email</Label><Input data-testid="invite-email-input" type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="recepcja@gabinet.pl" /></div>
            <div><Label>Imię (opcjonalnie)</Label><Input data-testid="invite-name-input" value={form.imie} onChange={(e) => setForm({ ...form, imie: e.target.value })} /></div>
            <Button type="submit" disabled={busy} data-testid="invite-submit-btn" className="w-full gap-2"><Mail className="h-4 w-4" /> Wyślij zaproszenie</Button>
          </form>
          {lastLink && (
            <div className="mt-4 p-3 rounded-lg bg-secondary/60 text-xs break-all" data-testid="invite-link-box">
              <div className="text-muted-foreground mb-1">Link zaproszenia (ważny 7 dni):</div>
              <div className="font-mono">{lastLink}</div>
              <Button size="sm" variant="ghost" className="mt-2 gap-1.5 h-7" data-testid="copy-invite-link-btn" onClick={() => { navigator.clipboard?.writeText(lastLink); toast.success("Skopiowano"); }}><Copy className="h-3 w-3" /> Kopiuj</Button>
            </div>
          )}
        </Card>

        <Card className="p-6 shadow-none lg:col-span-2">
          <div className="flex items-center gap-2 mb-4"><Users className="h-4 w-4 text-primary" /><h3 className="font-head font-semibold">Członkowie ({data.uzytkownicy.length})</h3></div>
          <div className="divide-y divide-border">
            {data.uzytkownicy.map((u) => (
              <div key={u.id} data-testid={`member-${u.id}`} className="py-3 flex items-center gap-3">
                <div className="h-9 w-9 rounded-full bg-primary/10 text-primary flex items-center justify-center font-semibold text-sm uppercase">{(u.imie || u.email)[0]}</div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium truncate">{u.imie || "—"} <span className="text-muted-foreground font-normal">· {u.email}</span></div>
                </div>
                {u.rola === "owner"
                  ? <Badge className="bg-amber-100 text-amber-800 hover:bg-amber-100 gap-1"><Crown className="h-3 w-3" /> Właściciel</Badge>
                  : <Badge variant="secondary">Recepcja</Badge>}
                {u.rola !== "owner" && <Button size="sm" variant="ghost" data-testid={`remove-member-${u.id}`} onClick={() => removeUser(u)} className="text-rose-600"><Trash2 className="h-4 w-4" /></Button>}
              </div>
            ))}
          </div>
          {data.zaproszenia.length > 0 && (
            <>
              <h4 className="text-sm font-medium mt-6 mb-2 text-muted-foreground">Oczekujące zaproszenia</h4>
              <div className="divide-y divide-border">
                {data.zaproszenia.map((i) => (
                  <div key={i.id} data-testid={`invite-${i.id}`} className="py-2.5 flex items-center gap-3 text-sm">
                    <Mail className="h-4 w-4 text-muted-foreground" />
                    <div className="flex-1">{i.email} {i.imie && <span className="text-muted-foreground">({i.imie})</span>}</div>
                    <span className="text-xs text-muted-foreground">wygasa {i.wygasa.slice(0, 10)}</span>
                    <Button size="sm" variant="ghost" data-testid={`cancel-invite-${i.id}`} onClick={() => cancelInvite(i)}><X className="h-4 w-4" /></Button>
                  </div>
                ))}
              </div>
            </>
          )}
        </Card>
      </div>
    </div>
  );
}

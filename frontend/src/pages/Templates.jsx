import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/Shared";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Save, Smartphone, Mail, BellRing } from "lucide-react";
import { toast } from "sonner";

const FIELDS = ["{imie}", "{nazwisko}", "{procedura}", "{interwal}", "{link_do_zapisu}", "{nazwa_gabinetu}"];
const FIELDS_24H = ["{imie}", "{data_wizyty}", "{godzina_wizyty}", "{nazwa_gabinetu}", "{adres}", "{telefon_gabinetu}"];

const preview = (tpl) =>
  (tpl || "")
    .replace(/{imie}/g, "Anna")
    .replace(/{nazwisko}/g, "Nowak")
    .replace(/{procedura}/g, "Higienizacja")
    .replace(/{interwal}/g, "6 miesięcy")
    .replace(/{link_do_zapisu}/g, "recalldent.pl/zapis/a1b2")
    .replace(/{nazwa_gabinetu}/g, "DentaMed")
    .replace(/{data_wizyty}/g, "24.06.2026")
    .replace(/{godzina_wizyty}/g, "10:30")
    .replace(/{adres}/g, "ul. Kwiatowa 12, Warszawa")
    .replace(/{telefon_gabinetu}/g, "+48 22 123 45 67");

export default function Templates() {
  const [t, setT] = useState({ sms: "", email_temat: "", email: "", sms_24h: "" });

  useEffect(() => { api.get("/templates").then((r) => setT(r.data)); }, []);

  const save = async () => {
    await api.put("/templates", { sms: t.sms, email_temat: t.email_temat, email: t.email, sms_24h: t.sms_24h });
    toast.success("Zapisano szablony");
  };

  return (
    <div data-testid="templates-page">
      <PageHeader
        title="Szablony wiadomości"
        subtitle="Edytuj treść SMS i email. Użyj pól dynamicznych podstawianych przy wysyłce."
        action={<Button data-testid="save-templates-btn" onClick={save} className="gap-2"><Save className="h-4 w-4" /> Zapisz</Button>}
      />

      <div className="mb-4 flex flex-wrap gap-2">
        {FIELDS.map((f) => <code key={f} className="text-xs px-2 py-1 rounded bg-secondary text-secondary-foreground font-mono">{f}</code>)}
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        <Card className="shadow-none p-5">
          <div className="flex items-center gap-2 mb-3">
            <Smartphone className="h-4 w-4 text-primary" />
            <h3 className="font-head font-semibold">Szablon SMS</h3>
          </div>
          <Textarea data-testid="sms-template" rows={5} value={t.sms || ""} onChange={(e) => setT({ ...t, sms: e.target.value })} />
          <div className="mt-3 p-3 rounded-lg bg-secondary/60 text-sm">
            <div className="text-xs text-muted-foreground mb-1">Podgląd:</div>
            {preview(t.sms)}
          </div>
        </Card>

        <Card className="shadow-none p-5">
          <div className="flex items-center gap-2 mb-3">
            <Mail className="h-4 w-4 text-primary" />
            <h3 className="font-head font-semibold">Szablon email</h3>
          </div>
          <Label className="text-xs">Temat</Label>
          <Input data-testid="email-subject" className="mb-3" value={t.email_temat || ""} onChange={(e) => setT({ ...t, email_temat: e.target.value })} />
          <Label className="text-xs">Treść</Label>
          <Textarea data-testid="email-template" rows={7} value={t.email || ""} onChange={(e) => setT({ ...t, email: e.target.value })} />
          <div className="mt-3 p-3 rounded-lg bg-secondary/60 text-sm whitespace-pre-wrap">
            <div className="text-xs text-muted-foreground mb-1">Podgląd:</div>
            {preview(t.email)}
          </div>
        </Card>

        <Card className="shadow-none p-5 lg:col-span-2" data-testid="sms-24h-card">
          <div className="flex items-center gap-2 mb-1">
            <BellRing className="h-4 w-4 text-primary" />
            <h3 className="font-head font-semibold">SMS przypominający 24h przed wizytą</h3>
          </div>
          <p className="text-sm text-muted-foreground mb-3">Wysyłany automatycznie o 09:00 dzień przed każdą zarezerwowaną wizytą (raz na wizytę), aby ograniczyć no-show.</p>
          <div className="mb-3 flex flex-wrap gap-2">
            {FIELDS_24H.map((f) => <code key={f} className="text-xs px-2 py-1 rounded bg-secondary text-secondary-foreground font-mono">{f}</code>)}
          </div>
          <Textarea data-testid="sms-24h-template" rows={4} value={t.sms_24h || ""} onChange={(e) => setT({ ...t, sms_24h: e.target.value })} />
          <div className="mt-3 p-3 rounded-lg bg-secondary/60 text-sm">
            <div className="text-xs text-muted-foreground mb-1">Podgląd:</div>
            {preview(t.sms_24h)}
          </div>
        </Card>
      </div>
    </div>
  );
}

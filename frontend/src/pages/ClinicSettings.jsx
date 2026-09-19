import { useEffect, useState } from "react";
import { api, apiError } from "@/lib/api";
import EmailSenderCard from "@/components/EmailSenderCard";
import { PageHeader } from "@/components/Shared";
import ReadOnlyBanner, { useIsOwner } from "@/components/ReadOnlyBanner";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Save, Building2, Clock } from "lucide-react";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";

export default function ClinicSettings() {
  const [s, setS] = useState(null);
  const isOwner = useIsOwner();

  useEffect(() => { api.get("/settings").then((r) => setS(r.data)); }, []);

  const save = async () => {
    const payload = {
      nazwa_gabinetu: s.nazwa_gabinetu, adres: s.adres, telefon: s.telefon,
      logo_url: s.logo_url, godzina_od: Number(s.godzina_od), godzina_do: Number(s.godzina_do), plan: s.plan,
      email_nadawca: (s.email_nadawca || "").trim(), email_reply_to: (s.email_reply_to || "").trim(),
    };
    if (s.resend_api_key && s.resend_api_key.trim()) payload.resend_api_key = s.resend_api_key.trim();
    try {
      const r = await api.put("/settings", payload);
      setS({ ...r.data, resend_api_key: "" });
      toast.success("Zapisano ustawienia gabinetu");
    } catch (e) {
      toast.error(apiError(e));
    }
  };

  if (!s) return null;
  const hours = Array.from({ length: 24 }, (_, i) => i);

  return (
    <div data-testid="clinic-settings-page">
      <PageHeader
        title="Ustawienia gabinetu"
        subtitle="Dane gabinetu, godziny wysyłki i plan subskrypcji"
        action={isOwner && <Button data-testid="save-settings-btn" onClick={save} className="gap-2"><Save className="h-4 w-4" /> Zapisz</Button>}
      />

      <ReadOnlyBanner />
      <div className="grid lg:grid-cols-2 gap-4">
        <Card className="shadow-none p-6">
          <div className="flex items-center gap-2 mb-4">
            <Building2 className="h-4 w-4 text-primary" />
            <h3 className="font-head font-semibold">Dane gabinetu</h3>
          </div>
          <div className="space-y-4">
            <div><Label>Nazwa gabinetu</Label><Input data-testid="setting-nazwa" value={s.nazwa_gabinetu || ""} onChange={(e) => setS({ ...s, nazwa_gabinetu: e.target.value })} /></div>
            <div><Label>Adres</Label><Input data-testid="setting-adres" value={s.adres || ""} onChange={(e) => setS({ ...s, adres: e.target.value })} /></div>
            <div><Label>Telefon</Label><Input data-testid="setting-telefon" value={s.telefon || ""} onChange={(e) => setS({ ...s, telefon: e.target.value })} /></div>
            <div><Label>URL logo (opcjonalnie)</Label><Input data-testid="setting-logo" value={s.logo_url || ""} onChange={(e) => setS({ ...s, logo_url: e.target.value })} placeholder="https://..." /></div>
          </div>
        </Card>

        <Card className="shadow-none p-6">
          <div className="flex items-center gap-2 mb-4">
            <Clock className="h-4 w-4 text-primary" />
            <h3 className="font-head font-semibold">Godziny wysyłki i plan</h3>
          </div>
          <p className="text-sm text-muted-foreground mb-4">Przypomnienia SMS/email są wysyłane tylko w podanym przedziale godzin.</p>
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div>
              <Label>Od godziny</Label>
              <Select value={String(s.godzina_od)} onValueChange={(v) => setS({ ...s, godzina_od: v })}>
                <SelectTrigger data-testid="setting-od"><SelectValue /></SelectTrigger>
                <SelectContent>{hours.map((h) => <SelectItem key={h} value={String(h)}>{h}:00</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div>
              <Label>Do godziny</Label>
              <Select value={String(s.godzina_do)} onValueChange={(v) => setS({ ...s, godzina_do: v })}>
                <SelectTrigger data-testid="setting-do"><SelectValue /></SelectTrigger>
                <SelectContent>{hours.map((h) => <SelectItem key={h} value={String(h)}>{h}:00</SelectItem>)}</SelectContent>
              </Select>
            </div>
          </div>
          <div>
            <Label>Plan subskrypcji</Label>
            <Select value={s.plan} onValueChange={(v) => setS({ ...s, plan: v })}>
              <SelectTrigger data-testid="setting-plan"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="Startowy">Startowy — 79 zł/mies (do 300 pacjentów, SMS)</SelectItem>
                <SelectItem value="Rozszerzony">Rozszerzony — 129 zł/mies (do 1000, SMS + email, ROI)</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </Card>

        <EmailSenderCard s={s} setS={setS} />
      </div>
    </div>
  );
}

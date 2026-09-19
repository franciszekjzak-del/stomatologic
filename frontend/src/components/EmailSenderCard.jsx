import { useState } from "react";
import { api, apiError } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Mail, Send, ShieldCheck, ExternalLink } from "lucide-react";
import { toast } from "sonner";

const STEPS = [
  "Załóż darmowe konto na resend.com i w zakładce Domains dodaj domenę gabinetu (np. twojgabinet.pl).",
  "Skopiuj wyświetlone rekordy DNS (SPF, DKIM, opcjonalnie DMARC) do panelu swojej domeny (home.pl, OVH, Cloudflare…).",
  "Poczekaj na status „Verified” (zwykle 5–30 min), a następnie w zakładce API Keys utwórz klucz z uprawnieniem Sending access.",
  "Wklej klucz poniżej, podaj adres nadawcy w zweryfikowanej domenie i wyślij wiadomość testową.",
];

export default function EmailSenderCard({ s, setS }) {
  const [testTo, setTestTo] = useState("");
  const [busy, setBusy] = useState(false);
  const own = s.resend_api_key_ustawiony && s.email_nadawca;

  const sendTest = async () => {
    setBusy(true);
    try {
      const r = await api.post("/settings/test-email", { do: testTo });
      toast.success(r.data.mock ? "Wysyłka w trybie symulacji (MOCK)" : `Wysłano testowy email (${r.data.provider === "resend_own" ? "własna domena" : "domena Emergent"})`);
    } catch (e) {
      toast.error(apiError(e));
    } finally { setBusy(false); }
  };

  return (
    <Card className="shadow-none p-6 lg:col-span-2" data-testid="email-sender-card">
      <div className="flex items-center justify-between gap-2 mb-2">
        <div className="flex items-center gap-2">
          <Mail className="h-4 w-4 text-primary" />
          <h3 className="font-head font-semibold">Domena nadawcy email</h3>
        </div>
        <span data-testid="email-sender-mode" className={`text-xs px-2.5 py-1 rounded-full font-medium ${own ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-800"}`}>
          {own ? `Własna domena: ${s.email_nadawca}` : "Domena Emergent (domyślna)"}
        </span>
      </div>
      <p className="text-sm text-muted-foreground mb-5">
        Maile do pacjentów mogą wychodzić z adresu Twojego gabinetu. Dopóki nie podasz klucza, używamy nadawcy zarządzanego przez Emergent.
      </p>

      <div className="grid md:grid-cols-2 gap-6">
        <div className="space-y-4">
          <div>
            <Label>Adres nadawcy (w zweryfikowanej domenie)</Label>
            <Input data-testid="setting-email-nadawca" placeholder="przypomnienia@twojgabinet.pl" value={s.email_nadawca || ""}
              onChange={(e) => setS({ ...s, email_nadawca: e.target.value })} />
          </div>
          <div>
            <Label>Klucz API Resend {s.resend_api_key_ustawiony && <span className="text-muted-foreground font-normal">(zapisany: {s.resend_api_key_podglad})</span>}</Label>
            <Input data-testid="setting-resend-key" type="password" placeholder={s.resend_api_key_ustawiony ? "Wpisz nowy, aby zmienić" : "re_..."}
              value={s.resend_api_key ?? ""} onChange={(e) => setS({ ...s, resend_api_key: e.target.value })} />
            <p className="text-xs text-muted-foreground mt-1">Zostaw puste, aby zachować obecny klucz. Klucz jest przechowywany po stronie serwera i nie jest pokazywany w całości.</p>
          </div>
          <div>
            <Label>Adres do odpowiedzi (reply-to, opcjonalnie)</Label>
            <Input data-testid="setting-reply-to" placeholder="recepcja@twojgabinet.pl" value={s.email_reply_to || ""}
              onChange={(e) => setS({ ...s, email_reply_to: e.target.value })} />
          </div>
          <div className="flex gap-2 pt-1">
            <Input data-testid="test-email-input" type="email" placeholder="Twój email do testu" value={testTo} onChange={(e) => setTestTo(e.target.value)} />
            <Button data-testid="test-email-btn" variant="outline" onClick={sendTest} disabled={busy || !testTo} className="gap-2 shrink-0">
              <Send className="h-4 w-4" /> Wyślij test
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">Test używa aktualnie <b>zapisanych</b> ustawień — najpierw kliknij „Zapisz”.</p>
        </div>

        <div className="rounded-xl bg-secondary/60 p-4">
          <div className="flex items-center gap-2 mb-3 text-sm font-medium">
            <ShieldCheck className="h-4 w-4 text-primary" /> Jak zweryfikować domenę w Resend
          </div>
          <ol className="space-y-2.5 text-sm text-muted-foreground list-decimal pl-5">
            {STEPS.map((t, i) => <li key={i}>{t}</li>)}
          </ol>
          <a href="https://resend.com/domains" target="_blank" rel="noreferrer" data-testid="resend-docs-link"
            className="inline-flex items-center gap-1.5 text-sm text-primary font-medium mt-4 hover:underline">
            Otwórz Resend → Domains <ExternalLink className="h-3.5 w-3.5" />
          </a>
        </div>
      </div>
    </Card>
  );
}

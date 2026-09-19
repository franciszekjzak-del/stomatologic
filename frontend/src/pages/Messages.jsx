import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/Shared";
import { Card } from "@/components/ui/card";
import { Smartphone, Mail, CheckCheck } from "lucide-react";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";

export default function Messages() {
  const [msgs, setMsgs] = useState([]);
  const [typ, setTyp] = useState("WSZYSTKIE");
  const [smsMode, setSmsMode] = useState(null);

  useEffect(() => {
    api.get("/reminders", { params: { typ } }).then((r) => setMsgs(r.data));
  }, [typ]);

  useEffect(() => { api.get("/sms-status").then((r) => setSmsMode(r.data)); }, []);

  return (
    <div data-testid="messages-page">
      <PageHeader
        title="Wysłane wiadomości"
        subtitle="Symulacja wysyłki (MOCK) — wiadomości nie są realnie wysyłane, tylko zapisywane do podglądu"
        action={
          <Select value={typ} onValueChange={setTyp}>
            <SelectTrigger data-testid="filter-msg-type" className="w-40"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="WSZYSTKIE">Wszystkie</SelectItem>
              <SelectItem value="SMS">SMS</SelectItem>
              <SelectItem value="EMAIL">Email</SelectItem>
            </SelectContent>
          </Select>
        }
      />

      {smsMode && (
        <div data-testid="sms-mode-banner" className="mb-4 grid sm:grid-cols-2 gap-3">
          <div className={`rounded-xl border p-3 text-sm flex items-start gap-2.5 ${
            smsMode.skonfigurowane ? "bg-emerald-50 border-emerald-200 text-emerald-800" : "bg-amber-50 border-amber-200 text-amber-800"
          }`}>
            <Smartphone className="h-4 w-4 mt-0.5 shrink-0" />
            <div><b>SMS: {smsMode.tryb}</b> ({smsMode.provider}). {smsMode.skonfigurowane ? "Realna wysyłka SMS." : "Symulacja — dodaj klucze Twilio, aby wysyłać realne SMS."}</div>
          </div>
          <div className={`rounded-xl border p-3 text-sm flex items-start gap-2.5 ${
            smsMode.email_skonfigurowane ? "bg-emerald-50 border-emerald-200 text-emerald-800" : "bg-amber-50 border-amber-200 text-amber-800"
          }`}>
            <Mail className="h-4 w-4 mt-0.5 shrink-0" />
            <div><b>Email: {smsMode.email_tryb}</b> ({smsMode.email_provider}). {smsMode.email_skonfigurowane ? "Realna wysyłka email." : "Symulacja email."}</div>
          </div>
        </div>
      )}

      <div className="space-y-3">
        {msgs.map((m) => (
          <Card key={m.id} data-testid={`message-${m.id}`} className="p-4 shadow-none flex gap-4">
            <div className={`h-10 w-10 rounded-xl flex items-center justify-center shrink-0 ${m.typ === "SMS" ? "bg-sky-50 text-sky-600" : "bg-violet-50 text-violet-600"}`}>
              {m.typ === "SMS" ? <Smartphone className="h-5 w-5" /> : <Mail className="h-5 w-5" />}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1 flex-wrap">
                <span className="font-medium text-sm">{m.pacjent_imie}</span>
                <span className="text-xs text-muted-foreground">{m.odbiorca}</span>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 font-medium">MOCK</span>
              </div>
              <p className="text-sm text-muted-foreground whitespace-pre-wrap break-words">{m.tresc}</p>
              <div className="flex items-center gap-1.5 mt-2 text-xs text-emerald-600">
                <CheckCheck className="h-3.5 w-3.5" /> Wysłano · {(m.data_wyslania || "").slice(0, 16).replace("T", " ")}
              </div>
            </div>
          </Card>
        ))}
        {msgs.length === 0 && <div className="text-center py-16 text-muted-foreground">Brak wiadomości</div>}
      </div>
    </div>
  );
}

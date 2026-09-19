import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, apiError, TOKEN_KEY } from "@/lib/api";
import AuthShell from "@/components/AuthShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { KeyRound, Mail, UserPlus } from "lucide-react";

const ErrorBox = ({ msg, id }) => msg ? <div data-testid={id} className="text-sm text-rose-600 bg-rose-50 border border-rose-200 rounded-lg px-3 py-2">{msg}</div> : null;

export function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");
  const submit = async (e) => {
    e.preventDefault(); setError("");
    try { await api.post("/auth/forgot-password", { email }); setSent(true); } catch (err) { setError(apiError(err)); }
  };
  return (
    <AuthShell title="Nie pamiętasz hasła?" subtitle="Wyślemy link do ustawienia nowego hasła"
      footer={<Link to="/logowanie" data-testid="back-to-login-link" className="text-primary font-medium hover:underline">Wróć do logowania</Link>}>
      {sent ? (
        <div data-testid="forgot-sent" className="rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 p-4 text-sm">
          Jeśli konto istnieje, wysłaliśmy wiadomość na <b>{email}</b>. Sprawdź skrzynkę (także spam). Link jest ważny 1 godzinę.
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-4" data-testid="forgot-form">
          <div><Label htmlFor="email">Email</Label><Input id="email" type="email" required data-testid="forgot-email-input" value={email} onChange={(e) => setEmail(e.target.value)} /></div>
          <ErrorBox msg={error} id="forgot-error" />
          <Button type="submit" data-testid="forgot-submit-btn" className="w-full gap-2"><Mail className="h-4 w-4" /> Wyślij link</Button>
        </form>
      )}
    </AuthShell>
  );
}

export function ResetPassword() {
  const { token } = useParams();
  const navigate = useNavigate();
  const [pw, setPw] = useState({ a: "", b: "" });
  const [error, setError] = useState("");
  const submit = async (e) => {
    e.preventDefault(); setError("");
    if (pw.a !== pw.b) { setError("Hasła nie są identyczne"); return; }
    try {
      const { data } = await api.post("/auth/reset-password", { token, password: pw.a });
      localStorage.setItem(TOKEN_KEY, data.token);
      window.location.assign("/panel");
    } catch (err) { setError(apiError(err)); }
  };
  return (
    <AuthShell title="Ustaw nowe hasło" subtitle="Minimum 8 znaków"
      footer={<Link to="/logowanie" className="text-primary font-medium hover:underline">Wróć do logowania</Link>}>
      <form onSubmit={submit} className="space-y-4" data-testid="reset-form">
        <div><Label>Nowe hasło</Label><Input type="password" required minLength={8} data-testid="reset-password-input" value={pw.a} onChange={(e) => setPw({ ...pw, a: e.target.value })} /></div>
        <div><Label>Powtórz hasło</Label><Input type="password" required minLength={8} data-testid="reset-password2-input" value={pw.b} onChange={(e) => setPw({ ...pw, b: e.target.value })} /></div>
        <ErrorBox msg={error} id="reset-error" />
        <Button type="submit" data-testid="reset-submit-btn" className="w-full gap-2"><KeyRound className="h-4 w-4" /> Zapisz hasło i zaloguj</Button>
      </form>
      {navigate && null}
    </AuthShell>
  );
}

export function AcceptInvite() {
  const { token } = useParams();
  const [info, setInfo] = useState(null);
  const [form, setForm] = useState({ imie: "", password: "" });
  const [error, setError] = useState("");
  useEffect(() => {
    api.get(`/auth/invite/${token}`).then((r) => { setInfo(r.data); setForm((f) => ({ ...f, imie: r.data.imie || "" })); }).catch((e) => setError(apiError(e)));
  }, [token]);
  const submit = async (e) => {
    e.preventDefault(); setError("");
    try {
      const { data } = await api.post(`/auth/invite/${token}/accept`, form);
      localStorage.setItem(TOKEN_KEY, data.token);
      window.location.assign("/panel");
    } catch (err) { setError(apiError(err)); }
  };
  return (
    <AuthShell title="Dołącz do gabinetu" subtitle={info ? `${info.zapraszajacy} zaprasza Cię do panelu „${info.gabinet}” jako recepcja` : "Sprawdzanie zaproszenia..."}
      footer={<Link to="/logowanie" className="text-primary font-medium hover:underline">Masz już konto? Zaloguj się</Link>}>
      {info ? (
        <form onSubmit={submit} className="space-y-4" data-testid="invite-accept-form">
          <div><Label>Email</Label><Input value={info.email} disabled data-testid="invite-accept-email" /></div>
          <div><Label>Imię</Label><Input data-testid="invite-accept-name-input" value={form.imie} onChange={(e) => setForm({ ...form, imie: e.target.value })} /></div>
          <div><Label>Hasło (min. 8 znaków)</Label><Input type="password" required minLength={8} data-testid="invite-accept-password-input" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></div>
          <ErrorBox msg={error} id="invite-accept-error" />
          <Button type="submit" data-testid="invite-accept-submit-btn" className="w-full gap-2"><UserPlus className="h-4 w-4" /> Utwórz konto i wejdź</Button>
        </form>
      ) : <ErrorBox msg={error} id="invite-accept-error" />}
    </AuthShell>
  );
}

import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { apiError } from "@/lib/api";
import AuthShell from "@/components/AuthShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { UserPlus } from "lucide-react";

export default function Register() {
  const { user, register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ nazwa_gabinetu: "", imie: "", email: "", password: "", dane_demo: true });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to="/panel" replace />;

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      await register(form);
      navigate("/panel", { replace: true });
    } catch (err) {
      setError(apiError(err));
    } finally { setBusy(false); }
  };

  const f = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  return (
    <AuthShell
      title="Załóż konto gabinetu"
      subtitle="Konto właściciela z osobną, odizolowaną bazą pacjentów"
      footer={<>Masz już konto? <Link to="/logowanie" data-testid="go-login-link" className="text-primary font-medium hover:underline">Zaloguj się</Link></>}
    >
      <form onSubmit={submit} className="space-y-4" data-testid="register-form">
        <div>
          <Label htmlFor="nazwa">Nazwa gabinetu</Label>
          <Input id="nazwa" required data-testid="register-clinic-input" placeholder="np. Gabinet Stomatologiczny Uśmiech"
            value={form.nazwa_gabinetu} onChange={f("nazwa_gabinetu")} />
        </div>
        <div>
          <Label htmlFor="imie">Twoje imię (opcjonalnie)</Label>
          <Input id="imie" data-testid="register-name-input" value={form.imie} onChange={f("imie")} />
        </div>
        <div>
          <Label htmlFor="email">Email</Label>
          <Input id="email" type="email" required autoComplete="email" data-testid="register-email-input"
            value={form.email} onChange={f("email")} />
        </div>
        <div>
          <Label htmlFor="password">Hasło (min. 8 znaków)</Label>
          <Input id="password" type="password" required minLength={8} autoComplete="new-password" data-testid="register-password-input"
            value={form.password} onChange={f("password")} />
        </div>
        <label className="flex items-start gap-2.5 text-sm cursor-pointer">
          <Checkbox data-testid="register-demo-checkbox" checked={form.dane_demo}
            onCheckedChange={(v) => setForm({ ...form, dane_demo: !!v })} className="mt-0.5" />
          <span className="text-muted-foreground">Załaduj przykładowych pacjentów, żeby od razu zobaczyć jak działa panel</span>
        </label>
        {error && <div data-testid="register-error" className="text-sm text-rose-600 bg-rose-50 border border-rose-200 rounded-lg px-3 py-2">{error}</div>}
        <Button type="submit" disabled={busy} data-testid="register-submit-btn" className="w-full gap-2">
          <UserPlus className="h-4 w-4" /> {busy ? "Tworzenie konta..." : "Utwórz konto"}
        </Button>
      </form>
    </AuthShell>
  );
}

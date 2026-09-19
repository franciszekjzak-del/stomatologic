import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { apiError } from "@/lib/api";
import AuthShell from "@/components/AuthShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LogIn } from "lucide-react";

export default function Login() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to="/panel" replace />;

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      await login(form.email, form.password);
      navigate("/panel", { replace: true });
    } catch (err) {
      setError(apiError(err));
    } finally { setBusy(false); }
  };

  return (
    <AuthShell
      title="Zaloguj się do panelu"
      subtitle="Wprowadź dane konta gabinetu"
      footer={<>Nie masz konta? <Link to="/rejestracja" data-testid="go-register-link" className="text-primary font-medium hover:underline">Załóż konto gabinetu</Link></>}
    >
      <form onSubmit={submit} className="space-y-4" data-testid="login-form">
        <div>
          <Label htmlFor="email">Email</Label>
          <Input id="email" type="email" required autoComplete="email" data-testid="login-email-input"
            value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
        </div>
        <div>
          <Label htmlFor="password">Hasło</Label>
          <Input id="password" type="password" required autoComplete="current-password" data-testid="login-password-input"
            value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
        </div>
        <div className="text-right -mt-1">
          <Link to="/nie-pamietam-hasla" data-testid="forgot-password-link" className="text-xs text-primary hover:underline">Nie pamiętam hasła</Link>
        </div>
        {error && <div data-testid="login-error" className="text-sm text-rose-600 bg-rose-50 border border-rose-200 rounded-lg px-3 py-2">{error}</div>}
        <Button type="submit" disabled={busy} data-testid="login-submit-btn" className="w-full gap-2">
          <LogIn className="h-4 w-4" /> {busy ? "Logowanie..." : "Zaloguj się"}
        </Button>
      </form>
    </AuthShell>
  );
}

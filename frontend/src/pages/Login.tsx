import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useAuthContext } from "@/components/AuthProvider";
import { Button, TextField } from "@/ui";

export function Login() {
  const navigate = useNavigate();
  const { login, user, loading } = useAuthContext();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(email.trim(), password);
      navigate("/dashboard", { replace: true });
    } catch {
      setError("Credenciais inválidas.");
    } finally {
      setBusy(false);
    }
  };

  if (!loading && user) return <Navigate to="/dashboard" replace />;

  return (
    <div className="flex min-h-screen items-center justify-center bg-surface-variant p-4">
      <form onSubmit={submit} className="surface w-full max-w-sm space-y-4 p-6 shadow-e2">
        <div className="flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded bg-primary text-sm font-bold text-primary-fg">
            n
          </span>
          <span className="text-lg font-semibold text-slate-800">nbplatform</span>
        </div>
        <TextField
          label="E-mail"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          autoFocus
        />
        <TextField
          label="Senha"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        {error && <p className="text-xs text-red-600">{error}</p>}
        <Button type="submit" fullWidth loading={busy}>
          Entrar
        </Button>
      </form>
    </div>
  );
}

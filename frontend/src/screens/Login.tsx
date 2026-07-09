import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth";

export default function Login() {
  const { login, register } = useAuth();
  const nav = useNavigate();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      if (mode === "login") {
        await login(email, password);
      } else {
        await register(email, password, code);
      }
      nav("/");
    } catch {
      setError(
        mode === "login"
          ? "Invalid email or password"
          : "Registration failed — check your invite code",
      );
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-900 p-6 text-slate-100">
      <form onSubmit={submit} className="w-full max-w-sm space-y-4">
        <h1 className="text-2xl font-bold">Training App</h1>
        <input
          className="w-full rounded bg-slate-800 p-3"
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <input
          className="w-full rounded bg-slate-800 p-3"
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        {mode === "register" && (
          <input
            className="w-full rounded bg-slate-800 p-3"
            type="text"
            placeholder="Invite code"
            value={code}
            onChange={(e) => setCode(e.target.value)}
          />
        )}
        {error && <p className="text-sm text-rose-400">{error}</p>}
        <button className="w-full rounded bg-emerald-600 p-3 font-semibold hover:bg-emerald-500">
          {mode === "login" ? "Log in" : "Create account"}
        </button>
        <button
          type="button"
          onClick={() => {
            setMode(mode === "login" ? "register" : "login");
            setError(null);
          }}
          className="w-full text-sm text-slate-400 hover:text-slate-200"
        >
          {mode === "login" ? "Have an invite code? Register" : "Already have an account? Log in"}
        </button>
      </form>
    </div>
  );
}

import { useEffect, useState } from "react";

type Health = { status: string; app: string; environment: string };

function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/health")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(setHealth)
      .catch((e) => setError(String(e)));
  }, []);

  return (
    <main className="min-h-screen bg-slate-900 text-slate-100 flex flex-col items-center justify-center gap-6 p-6">
      <h1 className="text-3xl font-bold">Training App</h1>
      <p className="text-slate-400">Walking skeleton — Phase 0</p>
      <div className="rounded-xl border border-slate-700 bg-slate-800 px-6 py-4 text-sm">
        {health ? (
          <span className="text-emerald-400">
            API: {health.status} · {health.app} · {health.environment}
          </span>
        ) : error ? (
          <span className="text-rose-400">API unreachable: {error}</span>
        ) : (
          <span className="text-slate-400">Checking API…</span>
        )}
      </div>
    </main>
  );
}

export default App;

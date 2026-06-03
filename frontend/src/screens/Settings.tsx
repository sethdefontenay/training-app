import { useEffect, useState } from "react";
import { get, post, put } from "../api";

type Field = { key: string; label: string; set: boolean };
type Status = { connected: boolean; fields: Field[] };

export default function Settings() {
  const [status, setStatus] = useState<Status | null>(null);
  const [vals, setVals] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState<string | null>(null);

  const load = () => get<Status>("/settings/google-health").then(setStatus);
  useEffect(() => {
    load();
  }, []);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    await put("/settings/google-health", vals);
    setVals({});
    setMsg("Saved.");
    load();
  };

  const sync = async () => {
    setMsg(null);
    try {
      const r = await post<{ steps_synced: number; sleep_synced: number }>("/sync/steps-sleep");
      setMsg(`Synced ${r.steps_synced} step day(s), ${r.sleep_synced} sleep night(s).`);
    } catch {
      setMsg(
        status?.connected
          ? "Connection saved, but the live Google client isn't built yet."
          : "Not connected — save your OAuth credentials first.",
      );
    }
  };

  if (!status) return <p className="text-slate-400">Loading…</p>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Settings</h1>

      <section className="space-y-3 rounded bg-slate-800 p-4">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold">Google Health (steps &amp; sleep)</h2>
          <span className={status.connected ? "text-emerald-400" : "text-slate-400"}>
            {status.connected ? "Connected" : "Not connected"}
          </span>
        </div>
        <form onSubmit={save} className="space-y-2">
          {status.fields.map((f) => (
            <label key={f.key} className="block text-sm">
              <span className="text-slate-400">
                {f.label} {f.set && <span className="text-emerald-400">· set</span>}
              </span>
              <input
                type="password"
                placeholder={f.set ? "•••••• (leave blank to keep)" : ""}
                value={vals[f.key] ?? ""}
                onChange={(e) => setVals({ ...vals, [f.key]: e.target.value })}
                className="mt-1 w-full rounded bg-slate-700 px-2 py-1"
              />
            </label>
          ))}
          <div className="flex gap-2">
            <button className="rounded bg-emerald-600 px-3 py-1 text-sm font-semibold">Save</button>
            <button
              type="button"
              onClick={sync}
              className="rounded bg-slate-700 px-3 py-1 text-sm"
            >
              Sync now
            </button>
          </div>
        </form>
        {msg && <p className="text-sm text-amber-300">{msg}</p>}
        <p className="text-xs text-slate-500">
          Paste your Google Health API key. Saving it marks the connection ready.
        </p>
      </section>
    </div>
  );
}

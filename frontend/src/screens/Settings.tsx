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
    const outcome = new URLSearchParams(window.location.search).get("gh");
    const messages: Record<string, string> = {
      connected: "Connected to Google Health ✓",
      denied: "Google sign-in was cancelled.",
      bad_state: "Connect failed (state mismatch) — try again.",
      exchange_failed: "Google rejected the token exchange — check client ID/secret.",
      missing_client: "Save your client ID & secret first, then Connect.",
      no_refresh_token: "Connected, but no refresh token returned — revoke app access in your Google account and Connect again.",
    };
    if (outcome && messages[outcome]) {
      setMsg(messages[outcome]);
      window.history.replaceState({}, "", "/settings");
    }
  }, []);

  const connect = () => {
    window.location.href = "/api/v1/settings/google-health/authorize";
  };

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
          ? "Sync failed — check the server logs (token may need re-consent)."
          : "Not connected — save your client ID/secret, then Connect with Google.",
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
          <div className="flex flex-wrap gap-2">
            <button className="rounded bg-emerald-600 px-3 py-1 text-sm font-semibold">Save</button>
            <button
              type="button"
              onClick={connect}
              className="rounded bg-blue-600 px-3 py-1 text-sm font-semibold"
            >
              Connect with Google
            </button>
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
          Save your Google OAuth client ID &amp; secret, then <b>Connect with Google</b> to grant
          offline access once — the server captures a refresh token and renews automatically.
          (You can also paste a refresh token directly if you already have one.)
        </p>
      </section>
    </div>
  );
}

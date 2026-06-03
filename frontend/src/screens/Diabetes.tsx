import { useEffect, useState } from "react";
import { get, post } from "../api";

type Record_ = {
  window_start: string;
  window_end: string;
  glucose: { average: number | null; time_in_range_pct: number | null; count: number };
  insulin_events: number;
  pump_uploaded: boolean;
};

export default function Diabetes() {
  const [rec, setRec] = useState<Record_ | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [pulling, setPulling] = useState(false);

  const load = () => get<Record_>("/diabetes/record").then(setRec);
  useEffect(() => {
    load();
  }, []);

  const pull = async () => {
    setMsg(null);
    setPulling(true);
    try {
      const r = await post<{ glucose_synced: number; insulin_synced: number }>("/diabetes/sync");
      setMsg(`Pulled ${r.glucose_synced} glucose readings, ${r.insulin_synced} insulin events.`);
      load();
    } catch {
      setMsg("Pull failed — check your Tidepool login in Settings.");
    } finally {
      setPulling(false);
    }
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Diabetes record</h1>
        <button
          onClick={pull}
          disabled={pulling}
          className="rounded bg-emerald-600 px-4 py-2 text-sm font-semibold disabled:opacity-50"
        >
          {pulling ? "Pulling…" : "Pull from Tidepool"}
        </button>
      </div>

      {msg && <p className="text-sm text-amber-300">{msg}</p>}

      {rec && (
        <div className="space-y-1 text-sm">
          <p className="text-slate-400">
            {rec.window_start} → {rec.window_end}
          </p>
          <p>Glucose avg: {rec.glucose.average ?? "—"} mmol/L</p>
          <p>Time in range: {rec.glucose.time_in_range_pct ?? "—"}%</p>
          <p>Insulin events: {rec.insulin_events}</p>
        </div>
      )}
    </div>
  );
}

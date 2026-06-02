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

  const load = () => get<Record_>("/diabetes/record").then(setRec);
  useEffect(() => {
    load();
  }, []);

  const sync = async () => {
    setMsg(null);
    try {
      await post("/diabetes/sync");
      load();
    } catch {
      setMsg("Tidepool not connected yet (needs credentials).");
    }
  };

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Diabetes record</h1>
      <button onClick={sync} className="rounded bg-slate-800 px-3 py-1 text-sm">
        Pull from Tidepool
      </button>
      {msg && <p className="text-sm text-amber-300">{msg}</p>}
      {rec && (
        <div className="space-y-1 text-sm">
          <p className="text-slate-400">
            {rec.window_start} → {rec.window_end}
          </p>
          <p>Glucose avg: {rec.glucose.average ?? "—"} mmol/L</p>
          <p>Time in range: {rec.glucose.time_in_range_pct ?? "—"}%</p>
          <p>Insulin events: {rec.insulin_events}</p>
          {!rec.pump_uploaded && (
            <p className="text-amber-300">Pump not uploaded — run the Tidepool Uploader.</p>
          )}
        </div>
      )}
    </div>
  );
}

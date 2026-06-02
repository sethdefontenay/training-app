import { useState } from "react";
import { patch, post } from "../api";

type Metric = { values: { date: string; value: number }[]; average: number | null };
type View = {
  id: number;
  window_start: string;
  window_end: string;
  metrics: Record<string, Metric>;
  measurements: Record<string, number | null> | null;
  sessions_logged: number;
  completed: boolean;
};

export default function CheckIn() {
  const [ci, setCi] = useState<View | null>(null);
  const [worked, setWorked] = useState("");
  const [struggles, setStruggles] = useState("");

  const start = async () => setCi(await post<View>("/check-ins", {}));
  const saveReflections = async () => {
    if (!ci) return;
    await patch(`/check-ins/${ci.id}`, { worked_on: worked, struggles });
  };
  const finish = async () => {
    if (!ci) return;
    setCi(await post<View>(`/check-ins/${ci.id}/finish`));
  };

  if (!ci)
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold">Weekly check-in</h1>
        <button onClick={start} className="rounded bg-emerald-600 px-4 py-2 font-semibold">
          Start check-in (last 7 days)
        </button>
      </div>
    );

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Check-in</h1>
      <p className="text-sm text-slate-400">
        {ci.window_start} → {ci.window_end} · {ci.sessions_logged} sessions logged
      </p>

      <section>
        <h2 className="font-semibold">Wellbeing (7-day average)</h2>
        <ul className="text-sm">
          {Object.entries(ci.metrics).map(([k, m]) => (
            <li key={k} className="flex justify-between">
              <span className="capitalize">{k}</span>
              <span className="text-slate-400">
                {m.average ?? "—"} ({m.values.length} days logged)
              </span>
            </li>
          ))}
        </ul>
      </section>

      {ci.measurements && (
        <p className="text-sm text-slate-400">
          Latest waist {ci.measurements.waist_cm ?? "—"} · weight {ci.measurements.weight_kg ?? "—"}
        </p>
      )}

      <textarea
        placeholder="What I worked on this week"
        value={worked}
        onChange={(e) => setWorked(e.target.value)}
        onBlur={saveReflections}
        className="w-full rounded bg-slate-800 p-2"
      />
      <textarea
        placeholder="Struggles this week"
        value={struggles}
        onChange={(e) => setStruggles(e.target.value)}
        onBlur={saveReflections}
        className="w-full rounded bg-slate-800 p-2"
      />
      <button
        onClick={finish}
        className="rounded bg-emerald-600 px-4 py-2 font-semibold disabled:opacity-50"
        disabled={ci.completed}
      >
        {ci.completed ? "Completed ✓" : "Finish"}
      </button>
    </div>
  );
}

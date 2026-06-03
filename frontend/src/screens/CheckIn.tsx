import { useState } from "react";
import { get, patch, post, put, todayLocal } from "../api";

type Metric = { values: { date: string; value: number }[]; average: number | null };
type Sleep = { avg_efficiency: number | null; avg_asleep_min: number | null; nights: number };
type View = {
  id: number;
  window_start: string;
  window_end: string;
  metrics: Record<string, Metric>;
  latest_measurements: Record<string, number | null>;
  steps_avg: number | null;
  sleep: Sleep;
  sessions_logged: number;
  completed: boolean;
};

const FIELDS: [string, string][] = [
  ["waist_cm", "Waist"],
  ["tummy_cm", "Tummy"],
  ["bum_cm", "Bum"],
  ["right_thigh_cm", "R thigh"],
  ["left_thigh_cm", "L thigh"],
  ["weight_kg", "Weight"],
];

const today = todayLocal;

export default function CheckIn() {
  const [ci, setCi] = useState<View | null>(null);
  const [worked, setWorked] = useState("");
  const [struggles, setStruggles] = useState("");
  const [meas, setMeas] = useState<Record<string, string>>({});

  const start = async () => setCi(await post<View>("/check-ins", {}));
  const refresh = async () => ci && setCi(await get<View>(`/check-ins/${ci.id}`));
  const saveReflections = async () => {
    if (ci) await patch(`/check-ins/${ci.id}`, { worked_on: worked, struggles });
  };
  const finish = async () => {
    if (ci) setCi(await post<View>(`/check-ins/${ci.id}/finish`));
  };
  const saveMeasurements = async () => {
    const body: Record<string, unknown> = { date: today() };
    for (const [k] of FIELDS) if (meas[k]) body[k] = Number(meas[k]);
    await put("/measurements", body);
    setMeas({});
    refresh();
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

  const m = ci.latest_measurements;
  const mins = ci.sleep.avg_asleep_min;
  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-bold">Check-in</h1>
      <p className="text-sm text-slate-400">
        {ci.window_start} → {ci.window_end} · {ci.sessions_logged} sessions logged
      </p>

      <section>
        <h2 className="font-semibold">Wellbeing (7-day average)</h2>
        <ul className="text-sm">
          {Object.entries(ci.metrics).map(([k, met]) => (
            <li key={k} className="flex justify-between">
              <span className="capitalize">{k}</span>
              <span className="text-slate-400">
                {met.average ?? "—"} ({met.values.length} days)
              </span>
            </li>
          ))}
        </ul>
      </section>

      <section className="text-sm">
        <h2 className="mb-1 font-semibold">Recovery (7-day)</h2>
        <p className="text-slate-400">
          Avg steps/day: {ci.steps_avg ?? "—"} · Sleep:{" "}
          {mins != null ? `${Math.floor(mins / 60)}h ${Math.round(mins % 60)}m` : "—"} avg ·{" "}
          {ci.sleep.avg_efficiency ?? "—"}% efficiency ({ci.sleep.nights} nights)
        </p>
      </section>

      <section>
        <h2 className="mb-1 font-semibold">Last measurements</h2>
        <div className="grid grid-cols-3 gap-2 text-sm">
          {FIELDS.map(([k, label]) => (
            <div key={k} className="rounded bg-slate-800 px-2 py-1">
              <div className="text-slate-400">{label}</div>
              <div>{m[k] ?? "—"}</div>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2 className="mb-1 font-semibold">Enter today's measurements</h2>
        <div className="grid grid-cols-3 gap-2">
          {FIELDS.map(([k, label]) => (
            <label key={k} className="text-sm">
              <span className="text-slate-400">{label}</span>
              <input
                type="number"
                step="0.1"
                value={meas[k] ?? ""}
                onChange={(e) => setMeas({ ...meas, [k]: e.target.value })}
                className="mt-1 w-full rounded bg-slate-700 px-2 py-1"
              />
            </label>
          ))}
        </div>
        <button
          onClick={saveMeasurements}
          className="mt-2 rounded bg-emerald-600 px-3 py-1 text-sm font-semibold"
        >
          Save measurements
        </button>
      </section>

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

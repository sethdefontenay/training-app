import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { get, post, put } from "../api";

type Meal = { id: number; name: string; slot: string; carbs_g: number | null; eaten: boolean };
type Exercise = {
  slug: string;
  name: string;
  sets_x_reps: string;
  target_sets: number | null;
  completed_sets: number;
};
type DailyView = {
  date: string;
  weekday: string;
  has_plan: boolean;
  workout: { label: string; exercises: Exercise[] } | null;
  meals: Meal[];
  daily_carbs_total: number | null;
  steps: { steps: number | null; target: number | null };
  wellbeing: { energy: number | null; motivation: number | null; stress: number | null; hunger: number | null };
};

const today = () => new Date().toISOString().slice(0, 10);
const METRICS = ["energy", "motivation", "stress", "hunger"] as const;

export default function Today() {
  const day = today();
  const [view, setView] = useState<DailyView | null>(null);

  const load = () => get<DailyView>(`/daily/${day}`).then(setView);
  useEffect(() => {
    load();
  }, []);

  if (!view) return <p className="text-slate-400">Loading…</p>;

  const checkMeal = async (id: number) => {
    await post(`/daily/${day}/meals/${id}/check`);
    load();
  };
  const setMetric = async (k: string, v: number) => {
    await put(`/daily/${day}/wellbeing`, { [k]: v });
    load();
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">
        {view.weekday} <span className="text-slate-400">{view.date}</span>
      </h1>

      {view.workout ? (
        <section>
          <h2 className="mb-2 font-semibold">{view.workout.label}</h2>
          <ul className="space-y-1">
            {view.workout.exercises.map((e) => (
              <li key={e.slug} className="flex justify-between rounded bg-slate-800 px-3 py-2">
                <span>{e.name}</span>
                <span className="text-slate-400">
                  {e.completed_sets}/{e.target_sets ?? "?"} · {e.sets_x_reps}
                </span>
              </li>
            ))}
          </ul>
          <Link to="/workout" className="mt-2 inline-block text-sm text-emerald-400">
            Log sets →
          </Link>
        </section>
      ) : (
        <p className="text-slate-400">Rest day — no workout scheduled.</p>
      )}

      <section>
        <h2 className="mb-2 font-semibold">
          Meals{" "}
          {view.daily_carbs_total != null && (
            <span className="text-sm text-slate-400">· {view.daily_carbs_total} g carbs total</span>
          )}
        </h2>
        <ul className="space-y-1">
          {view.meals.map((m) => (
            <li key={m.id} className="flex items-center justify-between rounded bg-slate-800 px-3 py-2">
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={m.eaten} onChange={() => checkMeal(m.id)} />
                {m.name}
              </label>
              <span className="text-sm text-amber-300">{m.carbs_g ?? "—"} g carbs</span>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2 className="mb-2 font-semibold">How I feel (out of 10)</h2>
        <div className="grid grid-cols-2 gap-2">
          {METRICS.map((k) => (
            <label key={k} className="flex items-center justify-between rounded bg-slate-800 px-3 py-2 capitalize">
              {k}
              <input
                type="number"
                min={1}
                max={10}
                defaultValue={view.wellbeing[k] ?? undefined}
                onBlur={(e) => e.target.value && setMetric(k, Number(e.target.value))}
                className="w-16 rounded bg-slate-700 px-2 py-1 text-right"
              />
            </label>
          ))}
        </div>
      </section>

      <p className="text-sm text-slate-400">
        Steps: {view.steps.steps ?? "—"} / {view.steps.target ?? "—"}
      </p>
    </div>
  );
}

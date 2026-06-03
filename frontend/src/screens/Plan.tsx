import { useEffect, useState } from "react";
import { ApiError, get } from "../api";

type Ex = { slug: string; name: string; sets_x_reps: string; prescribed_weight: string | null };
type Ingredient = { name: string; quantity: number | null; unit: string | null };
type Meal = {
  meal_number: number;
  slot: string;
  name: string;
  calories: number | null;
  protein_g: number | null;
  carbs_g: number | null;
  fat_g: number | null;
  ingredients: Ingredient[];
};
type Detail = {
  source: string | null;
  phase: number | null;
  start_date: string;
  days_since_start: number;
  targets: Record<string, number | null>;
  schedule: Record<string, [string | null, boolean]>;
  training_days: { label: string; exercises: Ex[] }[];
  meals: Meal[];
  mobility: string[];
};

const WEEKDAYS = [
  "monday",
  "tuesday",
  "wednesday",
  "thursday",
  "friday",
  "saturday",
  "sunday",
];

export default function Plan() {
  const [d, setD] = useState<Detail | null>(null);
  const [none, setNone] = useState(false);
  const [openMeal, setOpenMeal] = useState<number | null>(null);

  useEffect(() => {
    get<Detail>("/plans/current/detail")
      .then(setD)
      .catch((e) => {
        if (e instanceof ApiError && e.status === 404) setNone(true);
      });
  }, []);

  if (none) return <p className="text-slate-400">No active plan yet.</p>;
  if (!d) return <p className="text-slate-400">Loading…</p>;

  const t = d.targets;
  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold">{d.source ?? "Current plan"}</h1>
        <p className="text-sm text-slate-400">
          Started {d.start_date} · day {d.days_since_start}
          {d.phase != null && ` · phase ${d.phase}`}
        </p>
      </header>

      <section className="rounded bg-slate-800 p-3 text-sm">
        <h2 className="mb-1 font-semibold">Daily targets</h2>
        <p className="text-slate-300">
          {t.steps_target ?? "—"} steps · {t.water_min_l ?? "—"}–{t.water_max_l ?? "—"} L water ·{" "}
          {t.electrolytes_per_day ?? "—"} electrolytes
        </p>
        <p className="text-slate-300">
          {t.daily_calories ?? "—"} kcal · {t.daily_protein_g ?? "—"}P ·{" "}
          {t.daily_carbs_g ?? "—"}C · {t.daily_fat_g ?? "—"}F
        </p>
      </section>

      <section>
        <h2 className="mb-2 font-semibold">Weekly schedule</h2>
        <ul className="text-sm">
          {WEEKDAYS.map((wd) => {
            const [label, mob] = d.schedule[wd] ?? [null, false];
            return (
              <li key={wd} className="flex justify-between border-b border-slate-800 py-1">
                <span className="capitalize">{wd}</span>
                <span className="text-slate-400">
                  {label ?? "rest"}
                  {mob ? " · mobility" : ""}
                </span>
              </li>
            );
          })}
        </ul>
      </section>

      <section>
        <h2 className="mb-2 font-semibold">Training days</h2>
        {d.training_days.map((td) => (
          <div key={td.label} className="mb-3 rounded bg-slate-800 p-3">
            <div className="mb-1 font-semibold">{td.label}</div>
            <ul className="text-sm">
              {td.exercises.map((e) => (
                <li key={e.slug} className="flex justify-between">
                  <span>{e.name}</span>
                  <span className="text-slate-400">
                    {e.sets_x_reps}
                    {e.prescribed_weight ? ` · ${e.prescribed_weight} kg` : ""}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </section>

      <section>
        <h2 className="mb-2 font-semibold">Meals</h2>
        <ul className="space-y-1 text-sm">
          {d.meals.map((m) => {
            const open = openMeal === m.meal_number;
            return (
              <li key={m.meal_number} className="rounded bg-slate-800 px-3 py-2">
                <button
                  type="button"
                  onClick={() => setOpenMeal(open ? null : m.meal_number)}
                  className="w-full text-left"
                >
                  <div className="flex justify-between">
                    <span>
                      {open ? "▾" : "▸"} {m.name}
                    </span>
                    <span className="text-amber-300">{m.carbs_g ?? "—"} g carbs</span>
                  </div>
                  <div className="text-slate-400">
                    {m.calories ?? "—"} kcal · {m.protein_g ?? "—"}P · {m.fat_g ?? "—"}F
                  </div>
                </button>
                {open && (
                  <ul className="mt-2 border-t border-slate-700 pt-2">
                    {m.ingredients.length === 0 && (
                      <li className="text-slate-500">No ingredients recorded.</li>
                    )}
                    {m.ingredients.map((ing, i) => (
                      <li key={i} className="flex justify-between text-slate-300">
                        <span>{ing.name}</span>
                        <span className="text-slate-400">
                          {ing.quantity != null ? ing.quantity : ""} {ing.unit ?? ""}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            );
          })}
        </ul>
      </section>

      {d.mobility.length > 0 && (
        <section>
          <h2 className="mb-2 font-semibold">Mobility</h2>
          <p className="text-sm text-slate-400">{d.mobility.join(" · ")}</p>
        </section>
      )}
    </div>
  );
}

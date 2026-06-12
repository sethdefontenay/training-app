import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { del, get, post, put, shiftDay, todayLocal, weekdayOf } from "../api";

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
  mobility: { slug: string; name: string; done: boolean }[] | null;
  meals: Meal[];
  daily_carbs_total: number | null;
  steps: { steps: number | null; target: number | null };
  wellbeing: { energy: number | null; motivation: number | null; stress: number | null; hunger: number | null };
};

const today = todayLocal;
const METRICS = ["energy", "motivation", "stress", "hunger"] as const;

export default function Today() {
  const [day, setDay] = useState(today());
  const [view, setView] = useState<DailyView | null>(null);
  const isToday = day === today();

  const load = () => get<DailyView>(`/daily/${day}`).then(setView);
  // Reload whenever the selected day changes (and on first mount).
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [day]);

  useEffect(() => {
    // Low-overhead freshness: pull steps/sleep from Google Health in the
    // background on open (throttled to every 10 min), then refresh the view.
    // Silently ignore failures (e.g. Google Health not connected).
    const KEY = "lastHealthSync";
    const since = Date.now() - Number(localStorage.getItem(KEY) ?? 0);
    if (since > 10 * 60 * 1000) {
      localStorage.setItem(KEY, String(Date.now()));
      post("/sync/steps-sleep")
        .then(() => load())
        .catch(() => {});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Day navigation. Swipe right / "‹" = previous day (into the past); swipe
  // left / "›" = next day, capped at today (no logging the future).
  const goPrev = () => setDay((d) => shiftDay(d, -1));
  const goNext = () => setDay((d) => (d === today() ? d : shiftDay(d, 1)));
  const touchStart = useRef<{ x: number; y: number } | null>(null);
  const onTouchStart = (e: React.TouchEvent) => {
    const t = e.touches[0];
    touchStart.current = { x: t.clientX, y: t.clientY };
  };
  const onTouchEnd = (e: React.TouchEvent) => {
    const start = touchStart.current;
    touchStart.current = null;
    if (!start) return;
    const t = e.changedTouches[0];
    const dx = t.clientX - start.x;
    const dy = t.clientY - start.y;
    // Ignore taps and vertical scrolls; only act on a deliberate horizontal swipe.
    if (Math.abs(dx) < 60 || Math.abs(dx) < Math.abs(dy)) return;
    if (dx > 0) goPrev();
    else goNext();
  };

  // Header reflects the selected day immediately; the body dims while the new
  // day's data is in flight (view.date still holds the previously loaded day).
  const stale = !view || view.date !== day;

  const header = (
    <div className="flex items-center justify-between">
      <button
        onClick={goPrev}
        aria-label="Previous day"
        className="rounded px-3 py-1 text-xl text-slate-400 hover:bg-slate-800"
      >
        ‹
      </button>
      <h1 className="text-center text-2xl font-bold">
        {weekdayOf(day)} <span className="block text-sm font-normal text-slate-400">{day}</span>
      </h1>
      <button
        onClick={goNext}
        aria-label="Next day"
        disabled={isToday}
        className="rounded px-3 py-1 text-xl text-slate-400 hover:bg-slate-800 disabled:opacity-25"
      >
        ›
      </button>
    </div>
  );

  if (!view)
    return (
      <div onTouchStart={onTouchStart} onTouchEnd={onTouchEnd} className="space-y-6">
        {header}
        <p className="text-slate-400">Loading…</p>
      </div>
    );

  const toggleMeal = async (id: number, eaten: boolean) => {
    // Optimistic flip — the checkbox is controlled, so without this it snaps
    // back to its old state until the round-trip finishes (reads as "not working").
    setView((v) =>
      v ? { ...v, meals: v.meals.map((m) => (m.id === id ? { ...m, eaten: !eaten } : m)) } : v,
    );
    try {
      await (eaten
        ? del(`/daily/${day}/meals/${id}/check`)
        : post(`/daily/${day}/meals/${id}/check`));
    } finally {
      load(); // reconcile with server truth (reverts the flip if the call failed)
    }
  };
  const setMetric = async (k: string, v: number) => {
    await put(`/daily/${day}/wellbeing`, { [k]: v });
    load();
  };
  const toggleMobility = async (slug: string, done: boolean) => {
    setView((v) =>
      v
        ? { ...v, mobility: v.mobility?.map((m) => (m.slug === slug ? { ...m, done: !done } : m)) ?? null }
        : v,
    );
    try {
      await (done
        ? del(`/mobility/done?on=${day}&exercise_slug=${slug}`)
        : post(`/mobility/done`, { date: day, exercise_slug: slug }));
    } finally {
      load();
    }
  };

  return (
    <div onTouchStart={onTouchStart} onTouchEnd={onTouchEnd} className="space-y-6">
      {header}
      {!isToday && (
        <button
          onClick={() => setDay(today())}
          className="mx-auto block text-sm text-emerald-400"
        >
          Jump to today →
        </button>
      )}

      <div className={`space-y-6 transition-opacity ${stale ? "opacity-40" : ""}`}>
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

      {view.mobility && view.mobility.length > 0 && (
        <section>
          <h2 className="mb-2 font-semibold">Mobility</h2>
          <ul className="space-y-1">
            {view.mobility.map((m) => (
              <li key={m.slug} className="rounded bg-slate-800 px-3 py-2">
                <label className={`flex items-center gap-2 ${m.done ? "text-slate-500" : ""}`}>
                  <input
                    type="checkbox"
                    checked={m.done}
                    onChange={() => toggleMobility(m.slug, m.done)}
                  />
                  {m.name}
                </label>
              </li>
            ))}
          </ul>
        </section>
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
                <input
                  type="checkbox"
                  checked={m.eaten}
                  onChange={() => toggleMeal(m.id, m.eaten)}
                />
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
                key={`${day}-${k}`}
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
    </div>
  );
}

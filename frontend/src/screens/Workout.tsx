import { useEffect, useRef, useState } from "react";
import { get, post, todayLocal } from "../api";
import { useAuth } from "../auth";

type Ex = {
  slug: string;
  name: string;
  sets_x_reps: string;
  last_week: string;
  prescribed_weight: string | null;
  target_sets: number | null;
};
type DailyView = { workout: { label: string; exercises: Ex[] } | null };
type SetRead = { exercise_slug: string };
type SessionRead = { id: number; sets: SetRead[] };

const today = todayLocal;
const WORK_SECS = 60; // time to complete a set before the rest timer auto-starts
const REST_SECS = 90; // rest between sets

// Prescribed reps live in sets_x_reps like "4 × 15" or "3 × 10 per leg" — pull the
// first number after the "×" so each set logs the target rep count.
function prescribedReps(setsXReps: string): string {
  return setsXReps.split("×")[1]?.match(/\d+/)?.[0] ?? "";
}

// How many sets are prescribed — the target_sets from the plan, or the number before "×".
function prescribedSets(ex: Ex): number {
  if (ex.target_sets && ex.target_sets > 0) return ex.target_sets;
  const n = ex.sets_x_reps.split("×")[0]?.match(/\d+/)?.[0];
  return n ? Number(n) : 1;
}

// Default weight = the number from last week's top set ("40 kg" -> "40"); fall back to the
// prescribed weight, else blank (bodyweight).
function defaultWeight(ex: Ex): string {
  return ex.last_week?.match(/[\d.]+/)?.[0] ?? ex.prescribed_weight?.match(/[\d.]+/)?.[0] ?? "";
}

const mmss = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

export default function Workout() {
  const { readOnly } = useAuth();
  const day = today();
  const [exercises, setExercises] = useState<Ex[]>([]);
  const [label, setLabel] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<number | null>(null);
  // Sets already logged today per exercise slug — drives the completed ticks and lets the
  // runner resume mid-exercise. Seeded from today's session so revisiting doesn't reset it.
  const [logged, setLogged] = useState<Record<string, number>>({});
  const [loaded, setLoaded] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    get<DailyView>(`/daily/${day}`).then((v) => {
      setExercises(v.workout?.exercises ?? []);
      setLabel(v.workout?.label ?? null);
    });
    // Restore today's session (if started) so logged sets and the session id survive a revisit.
    get<SessionRead | null>(`/sessions/by-date/${day}`).then((s) => {
      if (s) {
        setSessionId(s.id);
        const counts: Record<string, number> = {};
        for (const set of s.sets) counts[set.exercise_slug] = (counts[set.exercise_slug] ?? 0) + 1;
        setLogged(counts);
      }
      setLoaded(true);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const ensureSession = async (): Promise<number> => {
    if (sessionId) return sessionId;
    // Idempotent on the backend: returns the existing day's session if there is one.
    const s = await post<{ id: number }>("/sessions", { date: day });
    setSessionId(s.id);
    return s.id;
  };

  const logSet = async (slug: string, reps: string, weight: string) => {
    const sid = await ensureSession();
    await post(`/sessions/${sid}/sets`, { exercise_slug: slug, reps, weight });
    setLogged((prev) => ({ ...prev, [slug]: (prev[slug] ?? 0) + 1 }));
  };

  if (!loaded) return <p className="text-slate-400">Loading…</p>;
  if (!exercises.length) return <p className="text-slate-400">No workout scheduled today.</p>;

  const selEx = exercises.find((e) => e.slug === selected);
  if (selEx && !readOnly) {
    return (
      <ExerciseRunner
        ex={selEx}
        initialDone={logged[selEx.slug] ?? 0}
        onLogSet={logSet}
        onBack={() => setSelected(null)}
      />
    );
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">{label ?? "Workout"}</h1>
      {readOnly && (
        <p className="text-sm text-slate-400">Read-only view of logged sets.</p>
      )}
      <ul className="space-y-2">
        {exercises.map((e) => {
          const target = prescribedSets(e);
          const done = logged[e.slug] ?? 0;
          const complete = done >= target;
          return (
            <li key={e.slug}>
              <button
                disabled={readOnly}
                onClick={() => setSelected(e.slug)}
                className="flex w-full items-center justify-between rounded-xl border border-slate-700 bg-slate-800 p-4 text-left hover:border-slate-500 disabled:cursor-default disabled:hover:border-slate-700"
              >
                <span className="font-semibold">{e.name}</span>
                <span className={`text-sm ${complete ? "text-emerald-400" : "text-slate-400"}`}>
                  {complete ? "✓ " : ""}
                  {done}/{target} sets
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

type Phase = "idle" | "working" | "resting" | "done";

function ExerciseRunner({
  ex,
  initialDone,
  onLogSet,
  onBack,
}: {
  ex: Ex;
  initialDone: number;
  onLogSet: (slug: string, reps: string, weight: string) => Promise<void>;
  onBack: () => void;
}) {
  const target = prescribedSets(ex);
  const reps = prescribedReps(ex.sets_x_reps);
  const [weight, setWeight] = useState(() => defaultWeight(ex));
  const [done, setDone] = useState(initialDone);
  const [phase, setPhase] = useState<Phase>(initialDone >= target ? "done" : "idle");
  const [secs, setSecs] = useState(0);
  const loggingRef = useRef(false);

  const finishSet = async () => {
    if (loggingRef.current) return; // guard against Done-tap racing the 0:00 auto-advance
    loggingRef.current = true;
    try {
      await onLogSet(ex.slug, reps, weight);
      const nd = done + 1;
      setDone(nd);
      if (nd >= target) {
        setPhase("done");
        setSecs(0);
      } else {
        setPhase("resting");
        setSecs(REST_SECS);
      }
    } finally {
      loggingRef.current = false;
    }
  };

  // One ticking timer for both the work and rest countdowns; at 0:00 it advances the phase.
  // The decrement/transition happen inside the deferred timeout, never in the effect body.
  useEffect(() => {
    if (phase !== "working" && phase !== "resting") return;
    const id = setTimeout(() => {
      if (secs > 0) {
        setSecs(secs - 1);
      } else if (phase === "working") {
        void finishSet(); // set's minute elapsed — log it and start the rest timer
      } else {
        setPhase("idle"); // rest over — wait for the user to start the next set
      }
    }, 1000);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase, secs]);

  const startSet = () => {
    setPhase("working");
    setSecs(WORK_SECS);
  };
  const skipRest = () => {
    setPhase("idle");
    setSecs(0);
  };

  return (
    <div className="space-y-4">
      <button onClick={onBack} className="text-sm text-slate-400 hover:text-slate-200">
        ← Exercises
      </button>

      <div className="space-y-4 rounded-xl border border-slate-700 bg-slate-800 p-4">
        <div className="flex items-baseline justify-between">
          <h2 className="text-xl font-bold">{ex.name}</h2>
          <span className="text-sm text-slate-400">last wk: {ex.last_week}</span>
        </div>
        <div className="text-sm text-slate-400">{ex.sets_x_reps}</div>

        <label className="flex items-center gap-2 text-sm">
          <span className="text-slate-400">Weight</span>
          <input
            inputMode="decimal"
            value={weight}
            onChange={(e) => setWeight(e.target.value)}
            placeholder="kg (blank = BW)"
            className="w-28 rounded bg-slate-700 px-2 py-1"
          />
          <span className="text-slate-500">kg — defaults to last time</span>
        </label>

        {/* One bar per prescribed set; filled as sets are logged. */}
        <div className="flex gap-1">
          {Array.from({ length: target }).map((_, i) => (
            <span
              key={i}
              className={`h-2 flex-1 rounded ${i < done ? "bg-emerald-500" : "bg-slate-600"}`}
            />
          ))}
        </div>

        {phase === "idle" && (
          <div className="space-y-3 text-center">
            <p className="text-slate-300">
              Set {done + 1} of {target}
              {reps ? ` · ${reps} reps` : ""}
            </p>
            <button
              onClick={startSet}
              className="w-full rounded bg-emerald-600 py-3 text-lg font-semibold"
            >
              {done === 0 ? "Start" : `Start set ${done + 1}`}
            </button>
          </div>
        )}

        {phase === "working" && (
          <div className="space-y-3 text-center">
            <p className="text-slate-400">
              Set {done + 1} of {target} — go!
            </p>
            <div className="font-mono text-6xl tabular-nums">{mmss(secs)}</div>
            <button
              onClick={() => void finishSet()}
              className="w-full rounded bg-emerald-600 py-3 text-lg font-semibold"
            >
              Done set
            </button>
          </div>
        )}

        {phase === "resting" && (
          <div className="space-y-3 text-center">
            <p className="text-slate-400">
              Rest — next: set {done + 1} of {target}
            </p>
            <div className="font-mono text-6xl tabular-nums text-sky-400">{mmss(secs)}</div>
            <button onClick={skipRest} className="w-full rounded bg-slate-700 py-2 text-sm">
              Skip rest
            </button>
          </div>
        )}

        {phase === "done" && (
          <div className="space-y-3 text-center">
            <p className="font-semibold text-emerald-400">All {target} sets done ✓</p>
            <button
              onClick={onBack}
              className="w-full rounded bg-emerald-600 py-3 text-lg font-semibold"
            >
              Finish
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

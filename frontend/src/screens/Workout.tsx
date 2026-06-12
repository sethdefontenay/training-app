import { useEffect, useState } from "react";
import { get, post, todayLocal } from "../api";

type Ex = { slug: string; name: string; sets_x_reps: string; last_week: string };
type DailyView = { workout: { label: string; exercises: Ex[] } | null };

const today = todayLocal;

export default function Workout() {
  const day = today();
  const [exercises, setExercises] = useState<Ex[]>([]);
  const [sessionId, setSessionId] = useState<number | null>(null);

  useEffect(() => {
    // Last-week numbers now ship with the daily view (one request), so there's no
    // per-exercise fan-out to wait on — the workout block renders in a single round-trip.
    get<DailyView>(`/daily/${day}`).then((v) => setExercises(v.workout?.exercises ?? []));
  }, []);

  const ensureSession = async (): Promise<number> => {
    if (sessionId) return sessionId;
    const s = await post<{ id: number }>("/sessions", { date: day });
    setSessionId(s.id);
    return s.id;
  };

  const logSet = async (slug: string, reps: string, weight: string) => {
    const sid = await ensureSession();
    await post(`/sessions/${sid}/sets`, { exercise_slug: slug, reps, weight });
  };

  if (!exercises.length) return <p className="text-slate-400">No workout scheduled today.</p>;

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Log workout</h1>
      {exercises.map((e) => (
        <Row key={e.slug} ex={e} last={e.last_week} onLog={logSet} />
      ))}
    </div>
  );
}

function Row({
  ex,
  last,
  onLog,
}: {
  ex: Ex;
  last: string;
  onLog: (slug: string, reps: string, weight: string) => Promise<void>;
}) {
  const [reps, setReps] = useState("");
  const [weight, setWeight] = useState("");
  const [done, setDone] = useState(0);
  return (
    <div className="rounded bg-slate-800 p-3">
      <div className="flex justify-between">
        <span className="font-semibold">{ex.name}</span>
        <span className="text-sm text-slate-400">last wk: {last}</span>
      </div>
      <div className="text-sm text-slate-400">
        {ex.sets_x_reps} · {done} logged
      </div>
      <div className="mt-2 flex gap-2">
        <input
          placeholder="reps"
          value={reps}
          onChange={(e) => setReps(e.target.value)}
          className="w-20 rounded bg-slate-700 px-2 py-1"
        />
        <input
          placeholder="kg (blank = BW)"
          value={weight}
          onChange={(e) => setWeight(e.target.value)}
          className="w-28 rounded bg-slate-700 px-2 py-1"
        />
        <button
          onClick={async () => {
            await onLog(ex.slug, reps, weight);
            setDone((d) => d + 1);
            // Keep reps/weight in the inputs — most sets repeat the same values,
            // so don't make Seth re-type them every set.
          }}
          className="rounded bg-emerald-600 px-3 py-1 text-sm"
        >
          + Set
        </button>
      </div>
    </div>
  );
}

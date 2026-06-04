import { useEffect, useState } from "react";
import { get } from "../api";

type ExerciseSets = { slug: string; name: string; sets: string[] };
type SessionSummary = { id: number; date: string; weekday: string | null; exercises: ExerciseSets[] };

export default function WorkoutHistory() {
  const [sessions, setSessions] = useState<SessionSummary[] | null>(null);

  useEffect(() => {
    get<SessionSummary[]>("/sessions").then(setSessions);
  }, []);

  if (sessions === null) return <p className="text-slate-400">Loading…</p>;

  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-bold">Workout history</h1>
      {sessions.length === 0 ? (
        <p className="text-slate-400">No workouts logged yet.</p>
      ) : (
        sessions.map((s) => (
          <section key={s.id} className="rounded-xl border border-slate-700 bg-slate-800/60 p-3">
            <h2 className="mb-2 font-semibold">
              {s.weekday} <span className="text-slate-400">{s.date}</span>
            </h2>
            <ul className="space-y-2">
              {s.exercises.map((e) => (
                <li key={e.slug}>
                  <div className="text-sm font-medium">{e.name}</div>
                  <div className="text-sm text-slate-400">{e.sets.join(" · ")}</div>
                </li>
              ))}
            </ul>
          </section>
        ))
      )}
    </div>
  );
}

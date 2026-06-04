import { useEffect, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { get } from "../api";

type PlanExercise = {
  slug: string;
  name: string;
  sets_x_reps: string;
  prescribed_weight: string | null;
};
type TrainingDay = { label: string; exercises: PlanExercise[] };
type PlanDetail = { training_days: TrainingDay[] };

type Point = { date: string; weight: number | null; reps: number | null; display: string };
type Progress = { slug: string; name: string; metric: "weight" | "reps"; points: Point[] };

const AXIS = "#94a3b8";
const LINE = "#38bdf8";
const mmdd = (d: string) => d.slice(5);

export default function ExerciseProgress() {
  const [days, setDays] = useState<TrainingDay[] | null>(null);
  const [sel, setSel] = useState<string | null>(null);
  const [prog, setProg] = useState<Progress | null>(null);

  useEffect(() => {
    get<PlanDetail>("/plans/current/detail")
      .then((d) => setDays(d.training_days))
      .catch(() => setDays([]));
  }, []);

  const select = (slug: string) => {
    setSel(slug);
    setProg(null);
    get<Progress>(`/workouts/exercises/${slug}/progress`).then(setProg);
  };

  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-bold">Exercise progress</h1>

      {sel && <ProgressPanel slug={sel} prog={prog} />}

      {days === null ? (
        <p className="text-slate-400">Loading…</p>
      ) : days.length === 0 ? (
        <p className="text-slate-400">No active plan — commit a plan first.</p>
      ) : (
        days.map((td) => (
          <section key={td.label}>
            <h2 className="mb-2 font-semibold">{td.label}</h2>
            <ul className="space-y-1">
              {td.exercises.map((e) => (
                <li key={e.slug}>
                  <button
                    onClick={() => select(e.slug)}
                    className={`flex w-full items-center justify-between rounded px-3 py-2 text-left ${
                      sel === e.slug ? "bg-sky-700" : "bg-slate-800 hover:bg-slate-700"
                    }`}
                  >
                    <span>{e.name}</span>
                    <span className="text-sm text-slate-400">{e.sets_x_reps}</span>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        ))
      )}
    </div>
  );
}

function ProgressPanel({ slug, prog }: { slug: string; prog: Progress | null }) {
  if (!prog || prog.slug !== slug) {
    return <p className="text-slate-400">Loading…</p>;
  }
  if (prog.points.length === 0) {
    return (
      <div className="rounded-xl border border-slate-700 bg-slate-800 p-4">
        <div className="font-semibold">{prog.name}</div>
        <p className="text-sm text-slate-400">No logged sets yet — log a workout to see progress.</p>
      </div>
    );
  }
  const unit = prog.metric === "weight" ? "kg" : "reps";
  const last = prog.points[prog.points.length - 1];
  const first = prog.points[0];
  return (
    <div className="space-y-2 rounded-xl border border-slate-700 bg-slate-800/60 p-3">
      <div className="flex items-baseline justify-between">
        <span className="font-semibold">{prog.name}</span>
        <span className="text-sm text-slate-400">
          {first.display} → {last.display}
        </span>
      </div>
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={prog.points} margin={{ top: 8, right: 8, bottom: 4, left: -16 }}>
          <CartesianGrid stroke="#1e293b" />
          <XAxis
            dataKey="date"
            tickFormatter={mmdd}
            tick={{ fill: AXIS, fontSize: 11 }}
            minTickGap={16}
          />
          <YAxis domain={["auto", "auto"]} tick={{ fill: AXIS, fontSize: 11 }} width={40} />
          <Tooltip
            contentStyle={{ background: "#0f172a", border: "1px solid #334155", fontSize: 12 }}
            formatter={(v) => [`${v} ${unit}`, prog.metric === "weight" ? "Top weight" : "Best reps"]}
          />
          <Line
            dataKey={prog.metric}
            stroke={LINE}
            strokeWidth={2}
            dot={{ r: 3 }}
            connectNulls
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
      <p className="text-xs text-slate-500">
        {prog.metric === "weight" ? "Heaviest set per workout (kg)" : "Best reps per workout"}
      </p>
    </div>
  );
}

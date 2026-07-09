import { useEffect, useState } from "react";
import { del, get, post, put } from "../api";

type ProgramExercise = {
  id: number;
  exercise_slug: string;
  exercise_name: string;
  sets_x_reps: string;
  prescribed_weight: string | null;
};
type Program = { id: number; name: string; exercises: ProgramExercise[] };
type Schedule = { weekday: string; program_id: number }[];

const WEEKDAYS = [
  "monday",
  "tuesday",
  "wednesday",
  "thursday",
  "friday",
  "saturday",
  "sunday",
];

export default function Planner() {
  const [programs, setPrograms] = useState<Program[]>([]);
  const [schedule, setSchedule] = useState<Schedule>([]);
  const [newName, setNewName] = useState("");
  const [busy, setBusy] = useState(false);

  const load = () =>
    Promise.all([
      get<Program[]>("/programs"),
      get<Schedule>("/programs/schedule"),
    ]).then(([progs, sched]) => {
      setPrograms(progs);
      setSchedule(sched);
    });
  useEffect(() => {
    load();
  }, []);

  const createProgram = async () => {
    if (!newName.trim()) return;
    await post("/programs", { name: newName.trim() });
    setNewName("");
    await load();
  };
  const deleteProgram = async (id: number) => {
    await del(`/programs/${id}`);
    await load();
  };
  const importPlan = async () => {
    setBusy(true);
    try {
      await post("/programs/import-training-days");
      await load();
    } finally {
      setBusy(false);
    }
  };
  const assignWeekday = async (weekday: string, programId: number | null) => {
    await put(`/programs/schedule/${weekday}`, { program_id: programId });
    await load();
  };

  const assignedFor = (weekday: string): number | null =>
    schedule.find((s) => s.weekday === weekday)?.program_id ?? null;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Workout planner</h1>
        <button
          onClick={importPlan}
          disabled={busy}
          className="rounded bg-slate-700 px-3 py-1 text-sm hover:bg-slate-600 disabled:opacity-50"
        >
          {busy ? "Importing…" : "Import my training days"}
        </button>
      </div>

      {/* Weekly schedule */}
      <section className="space-y-2">
        <h2 className="font-semibold text-slate-300">This week</h2>
        <div className="grid gap-2">
          {WEEKDAYS.map((wd) => (
            <div key={wd} className="flex items-center gap-3 rounded bg-slate-800 px-3 py-2">
              <span className="w-24 capitalize">{wd}</span>
              <select
                value={assignedFor(wd) ?? ""}
                onChange={(e) =>
                  assignWeekday(wd, e.target.value ? Number(e.target.value) : null)
                }
                className="flex-1 rounded bg-slate-900 p-2"
              >
                <option value="">— (fall back to PT plan) —</option>
                {programs.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </div>
          ))}
        </div>
      </section>

      {/* Programs */}
      <section className="space-y-3">
        <h2 className="font-semibold text-slate-300">My programs</h2>
        <div className="flex gap-2">
          <input
            className="flex-1 rounded bg-slate-800 p-2"
            placeholder="New program name"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && createProgram()}
          />
          <button
            onClick={createProgram}
            className="rounded bg-emerald-600 px-4 font-semibold hover:bg-emerald-500"
          >
            Add
          </button>
        </div>
        {programs.map((p) => (
          <ProgramCard key={p.id} program={p} onChanged={load} onDelete={deleteProgram} />
        ))}
        {programs.length === 0 && (
          <p className="text-sm text-slate-400">
            No programs yet — create one, or import your PT training days.
          </p>
        )}
      </section>
    </div>
  );
}

function ProgramCard({
  program,
  onChanged,
  onDelete,
}: {
  program: Program;
  onChanged: () => Promise<void>;
  onDelete: (id: number) => Promise<void>;
}) {
  const [slug, setSlug] = useState("");
  const [setsReps, setSetsReps] = useState("");
  const [weight, setWeight] = useState("");

  const addExercise = async () => {
    if (!slug.trim() || !setsReps.trim()) return;
    await post(`/programs/${program.id}/exercises`, {
      exercise_slug: slug.trim().toLowerCase().replace(/\s+/g, "-"),
      sets_x_reps: setsReps.trim(),
      prescribed_weight: weight.trim() || null,
    });
    setSlug("");
    setSetsReps("");
    setWeight("");
    await onChanged();
  };
  const removeExercise = async (peId: number) => {
    await del(`/programs/${program.id}/exercises/${peId}`);
    await onChanged();
  };

  return (
    <div className="space-y-2 rounded-xl border border-slate-700 bg-slate-800 p-3">
      <div className="flex items-center justify-between">
        <span className="font-semibold">{program.name}</span>
        <button
          onClick={() => onDelete(program.id)}
          className="text-sm text-rose-400 hover:text-rose-300"
        >
          Delete
        </button>
      </div>
      <ul className="space-y-1">
        {program.exercises.map((e) => (
          <li key={e.id} className="flex items-center justify-between text-sm">
            <span>
              {e.exercise_name} — {e.sets_x_reps}
              {e.prescribed_weight ? ` @ ${e.prescribed_weight} kg` : ""}
            </span>
            <button
              onClick={() => removeExercise(e.id)}
              className="text-slate-400 hover:text-rose-300"
            >
              ✕
            </button>
          </li>
        ))}
      </ul>
      <div className="flex flex-wrap gap-2">
        <input
          className="min-w-32 flex-1 rounded bg-slate-900 p-2 text-sm"
          placeholder="Exercise (e.g. Bench Press)"
          value={slug}
          onChange={(e) => setSlug(e.target.value)}
        />
        <input
          className="w-24 rounded bg-slate-900 p-2 text-sm"
          placeholder="4 × 8"
          value={setsReps}
          onChange={(e) => setSetsReps(e.target.value)}
        />
        <input
          className="w-20 rounded bg-slate-900 p-2 text-sm"
          placeholder="kg"
          value={weight}
          onChange={(e) => setWeight(e.target.value)}
        />
        <button
          onClick={addExercise}
          className="rounded bg-slate-700 px-3 text-sm hover:bg-slate-600"
        >
          Add exercise
        </button>
      </div>
    </div>
  );
}

import { Link } from "react-router-dom";
import { useAuth } from "../auth";

const AREAS = [
  { to: "/today", label: "Today", hint: "activities, meals & wellbeing", primary: true },
  { to: "/shopping", label: "Weekly shopping list", hint: "" },
  { to: "/check-in", label: "Weekly check-in", hint: "for your PT" },
  { to: "/measurements", label: "Measurements", hint: "" },
  { to: "/diabetes", label: "Diabetes record", hint: "glucose & insulin" },
  { to: "/sleep", label: "Sleep", hint: "stages per night & weekly trends" },
  { to: "/exercises", label: "Exercise progress", hint: "weight over time by workout day" },
  { to: "/history", label: "Workout history", hint: "past sessions & sets" },
  { to: "/plan", label: "Current plan", hint: "" },
  { to: "/settings", label: "Settings", hint: "connect Google Health" },
];

export default function Home() {
  const { readOnly } = useAuth();
  // Trainers get a read-only view of everything except settings, which is hidden.
  const areas = readOnly ? AREAS.filter((a) => a.to !== "/settings") : AREAS;
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Home</h1>
      {readOnly && (
        <p className="rounded bg-slate-800 px-3 py-2 text-sm text-slate-400">
          Read-only coach view — you can see everything but can't make changes.
        </p>
      )}
      <div className="grid gap-3">
        {areas.map((a) => (
          <Link
            key={a.to}
            to={a.to}
            className={`rounded-xl border p-4 ${
              a.primary
                ? "border-emerald-600 bg-emerald-950/40"
                : "border-slate-700 bg-slate-800"
            } hover:border-slate-500`}
          >
            <div className="font-semibold">{a.label}</div>
            {a.hint && <div className="text-sm text-slate-400">{a.hint}</div>}
          </Link>
        ))}
      </div>
    </div>
  );
}

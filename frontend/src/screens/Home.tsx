import { Link } from "react-router-dom";

const AREAS = [
  { to: "/today", label: "Today", hint: "activities, meals & wellbeing", primary: true },
  { to: "/shopping", label: "Weekly shopping list", hint: "" },
  { to: "/check-in", label: "Weekly check-in", hint: "for your PT" },
  { to: "/measurements", label: "Measurements", hint: "" },
  { to: "/diabetes", label: "Diabetes record", hint: "glucose & insulin" },
  { to: "/plan", label: "Current plan", hint: "" },
];

export default function Home() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Home</h1>
      <div className="grid gap-3">
        {AREAS.map((a) => (
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

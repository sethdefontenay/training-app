import { Link } from "react-router-dom";
import { useAuth, type Capabilities } from "../auth";

// `cap` gates a tile on a capability flag; tiles with no `cap` are universal.
const AREAS: {
  to: string;
  label: string;
  hint: string;
  primary?: boolean;
  cap?: keyof Capabilities;
}[] = [
  { to: "/today", label: "Today", hint: "activities, meals & wellbeing", primary: true },
  { to: "/planner", label: "Workout planner", hint: "build & schedule your programs" },
  { to: "/shopping", label: "Weekly shopping list", hint: "" },
  { to: "/check-in", label: "Weekly check-in", hint: "for your PT", cap: "hasCheckins" },
  { to: "/measurements", label: "Measurements", hint: "" },
  { to: "/diabetes", label: "Diabetes record", hint: "glucose & insulin", cap: "hasDiabetes" },
  {
    to: "/sleep",
    label: "Sleep",
    hint: "stages per night & weekly trends",
    cap: "hasHealthIntegrations",
  },
  { to: "/exercises", label: "Exercise progress", hint: "weight over time by workout day" },
  { to: "/history", label: "Workout history", hint: "past sessions & sets" },
  { to: "/plan", label: "Current plan", hint: "" },
  {
    to: "/settings",
    label: "Settings",
    hint: "connect Google Health",
    cap: "hasHealthIntegrations",
  },
];

export default function Home() {
  const { caps } = useAuth();
  // Show a tile only when its capability is enabled (universal tiles have no cap).
  const areas = AREAS.filter((a) => !a.cap || caps[a.cap]);
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Home</h1>
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

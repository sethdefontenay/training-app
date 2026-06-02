import { useEffect, useState } from "react";
import { get } from "../api";

type PlanRow = { id: number; start_date: string; is_current: boolean; source: string | null };

export default function Plan() {
  const [plans, setPlans] = useState<PlanRow[]>([]);
  useEffect(() => {
    get<PlanRow[]>("/plans").then(setPlans);
  }, []);

  const current = plans.find((p) => p.is_current);

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Current plan</h1>
      {current ? (
        <div className="rounded bg-slate-800 p-3">
          <p className="font-semibold">{current.source ?? "Plan"}</p>
          <p className="text-sm text-slate-400">from {current.start_date}</p>
        </div>
      ) : (
        <p className="text-slate-400">No plan yet.</p>
      )}
      <p className="text-sm text-slate-500">
        New plans arrive from your PT by email and are set up by the ingestion agent
        (you review before it goes live).
      </p>
      {plans.length > 1 && (
        <div>
          <h2 className="mb-1 text-sm font-semibold text-slate-400">Past plans</h2>
          <ul className="text-sm text-slate-400">
            {plans
              .filter((p) => !p.is_current)
              .map((p) => (
                <li key={p.id}>
                  {p.source ?? "Plan"} — {p.start_date}
                </li>
              ))}
          </ul>
        </div>
      )}
    </div>
  );
}

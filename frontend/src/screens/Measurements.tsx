import { useEffect, useState } from "react";
import { get, post } from "../api";

const FIELDS = ["waist_cm", "tummy_cm", "bum_cm", "right_thigh_cm", "left_thigh_cm", "weight_kg"];
type Row = Record<string, number | string | null> & { date: string };

export default function Measurements() {
  const [rows, setRows] = useState<Row[]>([]);
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [vals, setVals] = useState<Record<string, string>>({});

  const load = () => get<Row[]>("/measurements").then(setRows);
  useEffect(() => {
    load();
  }, []);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    const body: Record<string, unknown> = { date };
    for (const f of FIELDS) if (vals[f]) body[f] = Number(vals[f]);
    await post("/measurements", body);
    setVals({});
    load();
  };

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Measurements</h1>
      <form onSubmit={save} className="space-y-2 rounded bg-slate-800 p-3">
        <input
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
          className="rounded bg-slate-700 px-2 py-1"
        />
        <div className="grid grid-cols-2 gap-2">
          {FIELDS.map((f) => (
            <label key={f} className="flex items-center justify-between text-sm">
              {f.replace(/_/g, " ")}
              <input
                type="number"
                step="0.1"
                value={vals[f] ?? ""}
                onChange={(e) => setVals({ ...vals, [f]: e.target.value })}
                className="w-20 rounded bg-slate-700 px-2 py-1 text-right"
              />
            </label>
          ))}
        </div>
        <button className="rounded bg-emerald-600 px-3 py-1 text-sm">Save</button>
      </form>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-slate-400">
            <th>Date</th>
            <th>Waist</th>
            <th>Weight</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.date} className="border-t border-slate-800">
              <td>{r.date}</td>
              <td>{r.waist_cm ?? "—"}</td>
              <td>{r.weight_kg ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

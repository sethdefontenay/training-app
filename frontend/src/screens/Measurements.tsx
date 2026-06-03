import { useEffect, useState } from "react";
import { get, post, todayLocal } from "../api";

const FIELDS: [string, string][] = [
  ["waist_cm", "Waist"],
  ["tummy_cm", "Tummy"],
  ["bum_cm", "Bum"],
  ["right_thigh_cm", "Right thigh"],
  ["left_thigh_cm", "Left thigh"],
  ["weight_kg", "Weight"],
];

type Row = Record<string, number | string | null> & { date: string };
type Detail = Row & { changes: Record<string, number> };

export default function Measurements() {
  const [rows, setRows] = useState<Row[]>([]);
  const [date, setDate] = useState(todayLocal());
  const [vals, setVals] = useState<Record<string, string>>({});
  const [detail, setDetail] = useState<Detail | null>(null);

  const load = () => get<Row[]>("/measurements").then((r) => setRows([...r].reverse()));
  useEffect(() => {
    load();
  }, []);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    const body: Record<string, unknown> = { date };
    for (const [f] of FIELDS) if (vals[f]) body[f] = Number(vals[f]);
    await post("/measurements", body);
    setVals({});
    load();
  };

  const openDetail = (d: string) => get<Detail>(`/measurements/${d}`).then(setDetail);

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
          {FIELDS.map(([f, label]) => (
            <label key={f} className="flex items-center justify-between text-sm">
              {label}
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

      <h2 className="font-semibold">History</h2>
      <p className="text-xs text-slate-500">Tap a date for that day's full detail.</p>
      <ul className="divide-y divide-slate-800 rounded bg-slate-800/40">
        {rows.map((r) => (
          <li key={r.date}>
            <button
              type="button"
              onClick={() => openDetail(r.date)}
              className="flex w-full justify-between px-3 py-2 text-left text-sm hover:bg-slate-800"
            >
              <span>{r.date}</span>
              <span className="text-slate-400">
                waist {r.waist_cm ?? "—"} · {r.weight_kg ?? "—"} kg
              </span>
            </button>
          </li>
        ))}
      </ul>

      {detail && (
        <div className="rounded-xl border border-slate-700 bg-slate-800 p-4">
          <div className="mb-2 flex items-center justify-between">
            <h3 className="font-semibold">{detail.date}</h3>
            <button onClick={() => setDetail(null)} className="text-sm text-slate-400">
              ✕ close
            </button>
          </div>
          <table className="w-full text-sm">
            <tbody>
              {FIELDS.map(([f, label]) => {
                const change = detail.changes?.[f];
                return (
                  <tr key={f} className="border-t border-slate-700">
                    <td className="py-1 text-slate-400">{label}</td>
                    <td className="py-1 text-right">{detail[f] ?? "—"}</td>
                    <td className="py-1 pl-3 text-right text-xs">
                      {change != null && (
                        <span className={change < 0 ? "text-emerald-400" : "text-amber-400"}>
                          {change > 0 ? "+" : ""}
                          {change}
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <p className="mt-2 text-xs text-slate-500">Change vs the previous measurement.</p>
        </div>
      )}
    </div>
  );
}

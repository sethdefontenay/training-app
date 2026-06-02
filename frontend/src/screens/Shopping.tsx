import { useEffect, useState } from "react";
import { get, patch, post } from "../api";

type Item = { id: number; name: string; quantity: number | null; unit: string | null; checked: boolean };
type List = { id: number; week_start: string; items: Item[] };

export default function Shopping() {
  const [list, setList] = useState<List | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () =>
    get<List>("/shopping")
      .then(setList)
      .catch(() => setError("No active plan yet."));
  useEffect(() => {
    load();
  }, []);

  if (error) return <p className="text-slate-400">{error}</p>;
  if (!list) return <p className="text-slate-400">Loading…</p>;

  const toggle = async (it: Item) => {
    await patch(`/shopping/items/${it.id}`, { checked: !it.checked });
    load();
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Shopping</h1>
        <button
          onClick={async () => {
            await post("/shopping/regenerate");
            load();
          }}
          className="rounded bg-slate-800 px-3 py-1 text-sm"
        >
          Regenerate
        </button>
      </div>
      <ul className="space-y-1">
        {list.items.map((it) => (
          <li key={it.id} className="rounded bg-slate-800 px-3 py-2">
            <label className={`flex gap-2 ${it.checked ? "text-slate-500 line-through" : ""}`}>
              <input type="checkbox" checked={it.checked} onChange={() => toggle(it)} />
              {it.quantity ?? ""} {it.unit ?? ""} {it.name}
            </label>
          </li>
        ))}
      </ul>
    </div>
  );
}

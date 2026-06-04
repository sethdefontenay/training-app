import { useCallback, useEffect, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { get, post } from "../api";

type DayPoint = { min: number; mmol_l: number | null; iob: number };
type Meal = { min: number; name: string; carbs_g: number | null };
type Workout = { start_min: number; end_min: number; label: string };
type DayGraph = {
  range: "day";
  date: string;
  points: DayPoint[];
  meals: Meal[];
  workouts: Workout[];
  tir_low: number;
  tir_high: number;
};
type TrendDay = { date: string; avg: number | null; tir_pct: number | null; count: number };
type TrendGraph = {
  range: "week" | "month";
  start: string;
  end: string;
  daily: TrendDay[];
  tir_low: number;
  tir_high: number;
};
type Graph = DayGraph | TrendGraph;

type Range = "day" | "week" | "month";
const RANGES: { key: Range; label: string }[] = [
  { key: "day", label: "1 day" },
  { key: "week", label: "1 week" },
  { key: "month", label: "1 month" },
];

const AXIS = "#94a3b8"; // slate-400
const BG = "#38bdf8"; // sky-400
const IOB = "#c084fc"; // purple-400

const hhmm = (m: number) =>
  `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
const mmdd = (d: string) => d.slice(5);

export default function Diabetes() {
  const [range, setRange] = useState<Range>("day");
  const [graph, setGraph] = useState<Graph | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [pulling, setPulling] = useState(false);

  const load = useCallback(
    () => get<Graph>(`/diabetes/graph?range=${range}`).then(setGraph),
    [range],
  );
  useEffect(() => {
    load();
  }, [load]);
  // Treat a graph whose range doesn't match the selected toggle as "still loading"
  // (avoids flashing the previous range's chart, without setState-in-effect).
  const ready = graph && graph.range === range;

  const pull = async () => {
    setMsg(null);
    setPulling(true);
    try {
      const r = await post<{ glucose_synced: number; insulin_synced: number }>("/diabetes/sync");
      setMsg(`Pulled ${r.glucose_synced} glucose readings, ${r.insulin_synced} insulin events.`);
      load();
    } catch {
      setMsg("Pull failed — check your Tidepool login in Settings.");
    } finally {
      setPulling(false);
    }
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Diabetes record</h1>
        <button
          onClick={pull}
          disabled={pulling}
          className="rounded bg-emerald-600 px-4 py-2 text-sm font-semibold disabled:opacity-50"
        >
          {pulling ? "Pulling…" : "Pull from Tidepool"}
        </button>
      </div>

      <div className="flex gap-2">
        {RANGES.map((r) => (
          <button
            key={r.key}
            onClick={() => setRange(r.key)}
            className={`rounded px-3 py-1 text-sm ${
              range === r.key ? "bg-sky-600 font-semibold" : "bg-slate-800 text-slate-300"
            }`}
          >
            {r.label}
          </button>
        ))}
      </div>

      {msg && <p className="text-sm text-amber-300">{msg}</p>}

      {!ready ? (
        <p className="text-slate-400">Loading…</p>
      ) : graph.range === "day" ? (
        <DayChart g={graph} />
      ) : (
        <TrendChart g={graph} />
      )}
    </div>
  );
}

function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-1">
      <span className="inline-block h-2 w-3 rounded" style={{ background: color }} />
      {label}
    </span>
  );
}

function DayChart({ g }: { g: DayGraph }) {
  const hasGlucose = g.points.some((p) => p.mmol_l != null);
  return (
    <div className="space-y-2">
      <ResponsiveContainer width="100%" height={320}>
        <LineChart data={g.points} margin={{ top: 8, right: 8, bottom: 4, left: -16 }}>
          <CartesianGrid stroke="#1e293b" />
          <ReferenceArea
            yAxisId="bg"
            y1={g.tir_low}
            y2={g.tir_high}
            fill="#10b981"
            fillOpacity={0.1}
          />
          {g.workouts.map((w, i) => (
            <ReferenceArea
              key={`w${i}`}
              x1={w.start_min}
              x2={w.end_min}
              fill="#f59e0b"
              fillOpacity={0.14}
            />
          ))}
          {g.meals.map((m, i) => (
            <ReferenceLine
              key={`m${i}`}
              x={m.min}
              yAxisId="bg"
              stroke="#34d399"
              strokeDasharray="3 3"
              label={{
                value: `🍽 ${m.carbs_g ?? "?"}g`,
                fill: "#34d399",
                fontSize: 10,
                position: "top",
              }}
            />
          ))}
          <XAxis
            dataKey="min"
            type="number"
            domain={[0, 1440]}
            ticks={[0, 180, 360, 540, 720, 900, 1080, 1260, 1440]}
            tickFormatter={hhmm}
            tick={{ fill: AXIS, fontSize: 11 }}
          />
          <YAxis yAxisId="bg" domain={[2, 16]} tick={{ fill: AXIS, fontSize: 11 }} width={40} />
          <YAxis
            yAxisId="iob"
            orientation="right"
            domain={[0, "auto"]}
            tick={{ fill: AXIS, fontSize: 11 }}
            width={32}
          />
          <Tooltip
            contentStyle={{ background: "#0f172a", border: "1px solid #334155", fontSize: 12 }}
            labelFormatter={(m) => hhmm(Number(m))}
            formatter={(v, name) =>
              v == null ? ["—", name] : [v, name === "mmol_l" ? "BG (mmol/L)" : "IOB (U)"]
            }
          />
          <Line
            yAxisId="bg"
            dataKey="mmol_l"
            stroke={BG}
            dot={false}
            connectNulls
            strokeWidth={2}
            isAnimationActive={false}
          />
          <Line
            yAxisId="iob"
            dataKey="iob"
            stroke={IOB}
            dot={false}
            strokeWidth={1.5}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
      <div className="flex flex-wrap gap-3 text-xs text-slate-400">
        <LegendDot color={BG} label="BG mmol/L" />
        <LegendDot color={IOB} label="IOB (units)" />
        <LegendDot color="#10b981" label="in range 3.9–10" />
        <LegendDot color="#f59e0b" label="workout" />
        <LegendDot color="#34d399" label="meal" />
      </div>
      {!hasGlucose && (
        <p className="text-sm text-slate-400">
          No glucose for this day yet — pull from Tidepool, or pick a different range.
        </p>
      )}
    </div>
  );
}

function TrendChart({ g }: { g: TrendGraph }) {
  const withData = g.daily.filter((d) => d.avg != null);
  const avg =
    withData.length > 0
      ? Math.round((withData.reduce((s, d) => s + (d.avg ?? 0), 0) / withData.length) * 10) / 10
      : null;
  return (
    <div className="space-y-2">
      <ResponsiveContainer width="100%" height={320}>
        <LineChart data={g.daily} margin={{ top: 8, right: 8, bottom: 4, left: -16 }}>
          <CartesianGrid stroke="#1e293b" />
          <ReferenceArea y1={g.tir_low} y2={g.tir_high} fill="#10b981" fillOpacity={0.1} />
          <XAxis
            dataKey="date"
            tickFormatter={mmdd}
            tick={{ fill: AXIS, fontSize: 11 }}
            minTickGap={16}
          />
          <YAxis domain={[2, 16]} tick={{ fill: AXIS, fontSize: 11 }} width={40} />
          <Tooltip
            contentStyle={{ background: "#0f172a", border: "1px solid #334155", fontSize: 12 }}
            formatter={(v, name) => [v ?? "—", name === "avg" ? "Avg BG" : name]}
          />
          <Line
            dataKey="avg"
            stroke={BG}
            connectNulls
            strokeWidth={2}
            dot={{ r: 2 }}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
      <p className="text-sm text-slate-400">
        Average BG over period: <span className="text-slate-200">{avg ?? "—"}</span> mmol/L (
        {withData.length} day{withData.length === 1 ? "" : "s"} with data)
      </p>
    </div>
  );
}

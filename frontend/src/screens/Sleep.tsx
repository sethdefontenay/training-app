import { useCallback, useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { get } from "../api";

type Segment = {
  type: string;
  start_min: number;
  end_min: number;
  start_hm: string;
  end_hm: string;
};
type Night = {
  date: string;
  found: boolean;
  bedtime?: string | null;
  wake_time?: string | null;
  asleep_min?: number | null;
  efficiency?: number | null;
  deep_min?: number | null;
  light_min?: number | null;
  rem_min?: number | null;
  awake_min?: number | null;
  segments?: Segment[];
};
type TrendNight = {
  date: string;
  asleep_min: number | null;
  deep_min: number | null;
  light_min: number | null;
  rem_min: number | null;
  awake_min: number | null;
  efficiency: number | null;
};
type Trend = {
  nights: TrendNight[];
  averages: {
    asleep_min: number | null;
    efficiency: number | null;
    deep_min: number | null;
    light_min: number | null;
    rem_min: number | null;
    count: number;
  };
};

const STAGE: Record<string, { label: string; color: string }> = {
  deep: { label: "Deep", color: "#4f46e5" },
  light: { label: "Light", color: "#38bdf8" },
  rem: { label: "REM", color: "#a855f7" },
  awake: { label: "Awake", color: "#f59e0b" },
  out_of_bed: { label: "Out of bed", color: "#64748b" },
};
const AXIS = "#94a3b8";
const mmdd = (d: string) => d.slice(5);
const hm = (m: number | null | undefined) =>
  m == null ? "—" : `${Math.floor(m / 60)}h ${Math.round(m % 60)}m`;

export default function Sleep() {
  const [trend, setTrend] = useState<Trend | null>(null);
  const [night, setNight] = useState<Night | null>(null);

  const loadNight = useCallback((date?: string) => {
    get<Night>(`/sleep/night${date ? `?date=${date}` : ""}`).then(setNight);
  }, []);
  useEffect(() => {
    get<Trend>("/sleep/trend?days=14").then(setTrend);
    loadNight();
  }, [loadNight]);

  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-bold">Sleep</h1>
      {night && <NightCard night={night} onPick={loadNight} nights={trend?.nights ?? []} />}
      {trend && <TrendCard trend={trend} />}
    </div>
  );
}

function NightCard({
  night,
  nights,
  onPick,
}: {
  night: Night;
  nights: TrendNight[];
  onPick: (d: string) => void;
}) {
  const total = night.segments?.length
    ? Math.max(...night.segments.map((s) => s.end_min))
    : 0;
  return (
    <div className="space-y-3 rounded-xl border border-slate-700 bg-slate-800/60 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-semibold">Night of {night.date}</span>
        {nights.length > 0 && (
          <select
            value={night.date}
            onChange={(e) => onPick(e.target.value)}
            className="rounded bg-slate-700 px-2 py-1 text-sm"
          >
            {nights.map((n) => (
              <option key={n.date} value={n.date}>
                {n.date}
              </option>
            ))}
          </select>
        )}
      </div>

      {!night.found ? (
        <p className="text-sm text-slate-400">No sleep recorded for this night.</p>
      ) : (
        <>
          <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-slate-300">
            <span>
              {night.bedtime ?? "—"} → {night.wake_time ?? "—"}
            </span>
            <span>Asleep: {hm(night.asleep_min)}</span>
            <span>Efficiency: {night.efficiency != null ? `${night.efficiency}%` : "—"}</span>
          </div>

          {total > 0 ? (
            <>
              <div className="relative h-10 w-full overflow-hidden rounded bg-slate-900">
                {night.segments!.map((s, i) => (
                  <div
                    key={i}
                    title={`${STAGE[s.type]?.label ?? s.type} · ${s.start_hm}–${s.end_hm}`}
                    className="absolute top-0 h-full"
                    style={{
                      left: `${(s.start_min / total) * 100}%`,
                      width: `${((s.end_min - s.start_min) / total) * 100}%`,
                      background: STAGE[s.type]?.color ?? "#64748b",
                    }}
                  />
                ))}
              </div>
              <div className="flex justify-between text-xs text-slate-500">
                <span>{night.bedtime}</span>
                <span>{night.wake_time}</span>
              </div>
            </>
          ) : (
            <p className="text-sm text-slate-400">
              No stage detail for this night (synced before stage capture, or not reported by your
              tracker).
            </p>
          )}

          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {(["deep", "light", "rem", "awake"] as const).map((k) => (
              <div key={k} className="rounded bg-slate-900/60 px-2 py-1 text-sm">
                <span
                  className="mr-1 inline-block h-2 w-2 rounded-full align-middle"
                  style={{ background: STAGE[k].color }}
                />
                {STAGE[k].label}: {hm(night[`${k}_min` as keyof Night] as number | null)}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function TrendCard({ trend }: { trend: Trend }) {
  const data = trend.nights.map((n) => ({
    date: n.date,
    deep: n.deep_min,
    light: n.light_min,
    rem: n.rem_min,
    awake: n.awake_min,
  }));
  const a = trend.averages;
  return (
    <div className="space-y-2 rounded-xl border border-slate-700 bg-slate-800/60 p-3">
      <span className="font-semibold">Last {a.count} nights</span>
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={data} margin={{ top: 8, right: 8, bottom: 4, left: -16 }}>
          <CartesianGrid stroke="#1e293b" />
          <XAxis dataKey="date" tickFormatter={mmdd} tick={{ fill: AXIS, fontSize: 11 }} minTickGap={12} />
          <YAxis
            tick={{ fill: AXIS, fontSize: 11 }}
            width={40}
            tickFormatter={(v) => `${Math.round(Number(v) / 60)}h`}
          />
          <Tooltip
            contentStyle={{ background: "#0f172a", border: "1px solid #334155", fontSize: 12 }}
            formatter={(v, n) => [`${v} min`, STAGE[String(n)]?.label ?? n]}
          />
          <Legend formatter={(n) => STAGE[String(n)]?.label ?? n} wrapperStyle={{ fontSize: 11 }} />
          <Bar dataKey="deep" stackId="s" fill={STAGE.deep.color} />
          <Bar dataKey="light" stackId="s" fill={STAGE.light.color} />
          <Bar dataKey="rem" stackId="s" fill={STAGE.rem.color} />
          <Bar dataKey="awake" stackId="s" fill={STAGE.awake.color} />
        </BarChart>
      </ResponsiveContainer>
      <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-slate-300">
        <span>Avg asleep: <span className="text-slate-100">{hm(a.asleep_min)}</span></span>
        <span>Avg efficiency: <span className="text-slate-100">{a.efficiency ?? "—"}%</span></span>
        <span>Avg deep: {hm(a.deep_min)}</span>
        <span>Avg REM: {hm(a.rem_min)}</span>
      </div>
    </div>
  );
}

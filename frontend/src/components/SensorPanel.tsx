import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../api";
import { powerW, tempDiffK } from "../physics";
import { usePolling } from "../usePolling";

const AXIS = { stroke: "#5b6776", fontSize: 11, tickLine: false, axisLine: false } as const;
const TOOLTIP = {
  contentStyle: { background: "#121821", border: "1px solid #263140", borderRadius: 6, fontSize: 12 },
  labelStyle: { color: "#8b97a6" },
};

const time = (ts: string) => new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

interface Spec {
  key: string;
  title: string;
  unit: string;
  color: string;
  limit?: { value: number; label: string };
}

const SERIES: Spec[] = [
  { key: "tempDiff", title: "Process − air temp", unit: "K", color: "#4fb3ff", limit: { value: 8.6, label: "HDF 8.6 K" } },
  { key: "power", title: "Mechanical power", unit: "kW", color: "#f5a524", limit: { value: 9, label: "PWF 9 kW" } },
  { key: "torque", title: "Torque", unit: "Nm", color: "#b48cff" },
  { key: "rpm", title: "Spindle speed", unit: "rpm", color: "#3ecf8e", limit: { value: 1380, label: "1380 rpm" } },
  { key: "wear", title: "Tool wear", unit: "min", color: "#ff7a59", limit: { value: 200, label: "TWF 200" } },
];

export function SensorPanel({ machineId }: { machineId: string }) {
  const { data, error } = usePolling(() => api.readings(machineId, 60), 5000, [machineId]);
  const rows = (data?.readings ?? []).map((rec) => ({
    t: time(rec.ts),
    risk: Math.round(rec.prediction.risk * 100),
    tempDiff: +tempDiffK(rec.reading).toFixed(2),
    power: +(powerW(rec.reading) / 1000).toFixed(2),
    torque: rec.reading.torque_nm,
    rpm: rec.reading.rpm,
    wear: rec.reading.tool_wear_min,
  }));

  return (
    <section className="panel sensor-panel">
      <div className="panel-title">
        <h2>{machineId.toUpperCase()} · live telemetry</h2>
        <span className="muted">{rows.length} readings · refresh 5 s</span>
      </div>
      {error && <p className="error">{error}</p>}
      {rows.length === 0 ? (
        <p className="empty">Waiting for readings…</p>
      ) : (
        <>
          <div className="chart chart-risk">
            <h3>Failure risk (%)</h3>
            <ResponsiveContainer width="100%" height={150}>
              <AreaChart data={rows} margin={{ top: 6, right: 12, left: -18, bottom: 0 }}>
                <defs>
                  <linearGradient id="riskFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#ff4d4f" stopOpacity={0.55} />
                    <stop offset="100%" stopColor="#ff4d4f" stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="#1c2530" vertical={false} />
                <XAxis dataKey="t" {...AXIS} minTickGap={40} />
                <YAxis domain={[0, 100]} {...AXIS} />
                <Tooltip {...TOOLTIP} />
                <ReferenceLine y={50} stroke="#ff4d4f" strokeDasharray="4 4" />
                <Area type="monotone" dataKey="risk" stroke="#ff4d4f" fill="url(#riskFill)" strokeWidth={2}
                      isAnimationActive={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          <div className="chart-grid">
            {SERIES.map((s) => (
              <div className="chart" key={s.key}>
                <h3>{s.title} <span className="muted">({s.unit})</span></h3>
                <ResponsiveContainer width="100%" height={110}>
                  <LineChart data={rows} margin={{ top: 6, right: 8, left: -18, bottom: 0 }}>
                    <CartesianGrid stroke="#1c2530" vertical={false} />
                    <XAxis dataKey="t" {...AXIS} hide />
                    <YAxis {...AXIS} domain={["auto", "auto"]} width={52} />
                    <Tooltip {...TOOLTIP} />
                    {s.limit && (
                      <ReferenceLine y={s.limit.value} stroke="#ff4d4f" strokeOpacity={0.6} strokeDasharray="3 3" />
                    )}
                    <Line type="monotone" dataKey={s.key} stroke={s.color} dot={false} strokeWidth={1.8}
                          isAnimationActive={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            ))}
          </div>
        </>
      )}
    </section>
  );
}

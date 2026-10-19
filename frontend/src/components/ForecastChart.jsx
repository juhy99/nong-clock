import { Area, CartesianGrid, ComposedChart, Legend, Line, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { md, shortDate, won, wonPerKg } from "../utils/format";

/** 실제(history) + 예측(forecast)을 그래프 한 줄로 합친다 */
function toChartRows(p) {
  const rows = p.history.map((h) => ({ date: h.date, actual: h.price }));
  rows[rows.length - 1].forecast = p.base_price; // 실제선과 예측선이 이어지게
  rows[rows.length - 1].range = [p.base_price, p.base_price];
  p.forecast.forEach((f) => rows.push({ date: f.date, forecast: f.price, range: [f.lower, f.upper] }));
  return rows;
}

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="card" style={{ padding: "8px 12px", fontSize: 13 }}>
      <b>{shortDate(label)}</b>
      {row.actual != null && <div>실제 {wonPerKg(row.actual)}</div>}
      {row.forecast != null && row.actual == null && (
        <>
          <div style={{ color: "var(--green)" }}>예측 {wonPerKg(row.forecast)}</div>
          <div className="muted">범위 {won(row.range[0])} ~ {won(row.range[1])}원</div>
        </>
      )}
    </div>
  );
}

/** 실제 시세(검은 선) + 예측(초록 점선) + 오차범위 + 이상기후 구간. AI 예측 화면과 홈이 같이 쓴다. */
export default function ForecastChart({ p, height = 340, legend = true }) {
  const alert = p.alerts[0];
  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={toChartRows(p)} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
        <XAxis dataKey="date" tickFormatter={md} fontSize={12} minTickGap={16} />
        <YAxis fontSize={12} tickFormatter={won} width={60} domain={["auto", "auto"]} />
        <Tooltip content={<ChartTooltip />} />
        {legend && <Legend />}
        {alert && <ReferenceArea x1={alert.start} x2={alert.end} fill="#f9d9a6" fillOpacity={0.5} label={{ value: "이상기후", fontSize: 11, fill: "#9a6200" }} />}
        <Area name="예측 오차범위" dataKey="range" stroke="none" fill="#cfe8d7" fillOpacity={0.7} />
        <Line name="실제" dataKey="actual" stroke="#1c1c1a" strokeWidth={2} dot={false} />
        <Line name="예측" dataKey="forecast" stroke="#157a3e" strokeWidth={2.5} strokeDasharray="6 4" dot={false} />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

import { getSeasonal } from "../api/market";
import { Async, useAsync, useNarrow } from "./common";
import { won } from "../utils/format";

/* 가격 예측 화면 아래 "계절 패턴 · 월별 반입량" 두 카드 (11-12 샘플)
   계절 패턴: 월평균 경락가 — 평년(최근 5년 평균, 회색) · 올해 실제(검정) · 남은 달 예측(주황 점선)
   월별 반입량: 도매시장에 들어온 양(톤) — 평년 · 올해 (이번 달은 오늘까지라 속이 빈 점)
   데이터: getSeasonal(item) — Spring GET /api/prices/{item}/monthly (11-13, 철 밖 달 = 물량이 가장 많은 달의 2% 미만은 가격 비움) */
const C = { normal: "#7c867f", actual: "#13261a", forecast: "#d9600b" };
const niceStep = (range) => [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000].find((s) => range / s <= 5) ?? 50000;

function MonthChart({ lines, label, unit }) {
  const narrow = useNarrow();
  const W = narrow ? 420 : 640, H = narrow ? 300 : 280, L = narrow ? 58 : 66, R = 16, T = 18, B = 34;
  const vals = lines.flatMap((l) => l.data.filter((v) => v != null));
  if (!vals.length) return <p className="hint">이 품목은 월별 자료가 없어요.</p>;
  const step = niceStep(Math.max(...vals) - Math.min(0, ...vals) || 1);
  const lo = unit === "톤" ? 0 : Math.floor(Math.min(...vals) / step) * step; // 물량은 0부터
  const hi = Math.ceil(Math.max(...vals) / step) * step;
  const X = (m) => L + ((m - 1) * (W - L - R)) / 11;
  const Y = (v) => T + ((hi - v) / (hi - lo || 1)) * (H - T - B);
  const ticks = [];
  for (let v = lo; v <= hi; v += step) ticks.push(v);
  const path = (data) => data.map((v, i) => (v == null ? null : `${X(i + 1)},${Y(v)}`)).filter(Boolean).join(" ");
  return (
    <svg className="sc-chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label}>
      {ticks.map((v) => (
        <g key={v}>
          <line x1={L} x2={W - R} y1={Y(v)} y2={Y(v)} stroke="rgba(19,38,26,.08)" />
          <text x={L - 10} y={Y(v) + 5} textAnchor="end" fontSize="14" fill="rgba(19,38,26,.75)">{won(v)}</text>
        </g>
      ))}
      {Array.from({ length: 12 }, (_, i) => i + 1).filter((m) => !narrow || m % 2 === 1).map((m) => (
        <text key={m} x={X(m)} y={H - 8} textAnchor="middle" fontSize="14" fill="rgba(19,38,26,.75)">{m}월</text>
      ))}
      {lines.map((l) => (
        <g key={l.key}>
          <polyline points={path(l.data)} fill="none" stroke={l.color} strokeWidth={l.key === "normal" ? 2 : 2.5}
            strokeDasharray={l.dash ? "7 6" : undefined} strokeLinejoin="round" />
          {l.data.map((v, i) => v != null && !(l.dash && i === l.data.findIndex((x) => x != null)) && (
            <circle key={i} cx={X(i + 1)} cy={Y(v)} r={l.key === "normal" ? 3.5 : 4.5}
              fill={l.hollow === i + 1 ? "#fff" : l.color} stroke={l.color} strokeWidth="2" />
          ))}
        </g>
      ))}
    </svg>
  );
}

// 제목 · 범례 · 그래프만 (설명 줄 · 자료 줄 · 예시 데이터 표시는 11-13 뺌)
function Card({ title, legend, children }) {
  return (
    <section className="card sc-card">
      <div className="sc-head"><h2>{title}</h2></div>
      <div className="sc-legend">{legend.map(([t, c, dash]) => <span key={t}><i className={dash ? "dash" : ""} style={{ "--c": c }} />{t}</span>)}</div>
      {children}
    </section>
  );
}

export default function SeasonCharts({ item, itemName, anchor }) {
  const state = useAsync(() => getSeasonal(item, { anchor }), [item, anchor]);
  return (
    <Async state={state} minHeight={360}>
      {(d) => {
        return (
          <div className="sc-grid">
            <Card title="계절 패턴"
              legend={[["평년", C.normal], [`${d.year}년`, C.actual], ["예측", C.forecast, true]]}>
              <MonthChart unit="원" label={`${itemName} 월평균 경락가: 평년, ${d.year}년 실제와 예측`}
                lines={[
                  { key: "normal", data: d.price.normal, color: C.normal },
                  { key: "actual", data: d.price.actual, color: C.actual },
                  { key: "forecast", data: d.price.forecast, color: C.forecast, dash: true },
                ]} />
            </Card>
            <Card title="월별 반입량"
              legend={[["평년", C.normal], [`${d.year}년`, C.actual]]}>
              <MonthChart unit="톤" label={`${itemName} 월별 반입량: 평년과 ${d.year}년`}
                lines={[
                  { key: "normal", data: d.volume.normal, color: C.normal },
                  { key: "actual", data: d.volume.actual, color: C.actual, hollow: d.volume.partial_month },
                ]} />
            </Card>
          </div>
        );
      }}
    </Async>
  );
}

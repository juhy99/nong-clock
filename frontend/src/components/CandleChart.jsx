import { useEffect, useRef, useState } from "react";
import { md, won } from "../utils/format";

/** 부모 폭을 따라가는 SVG 폭 */
function useWidth() {
  const ref = useRef(null);
  const [w, setW] = useState(0);
  useEffect(() => {
    if (!ref.current) return undefined;
    const ro = new ResizeObserver(([e]) => setW(Math.round(e.contentRect.width)));
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);
  return [ref, w];
}

/**
 * 일별 캔들(시가 = 전 거래일 가격, 종가 = 그날 가격, 최고·최저) + 끝에 AI 예측(점선 + 오차 띠).
 * 오르면 빨강, 내리면 파랑 (주식 차트와 같은 색).
 * points: [{ date, open, close, high, low }]  forecast: [{ date, price, lower, upper }]
 */
export default function CandleChart({ points, forecast = [], height = 280 }) {
  const [ref, w] = useWidth();
  const axisW = 52, top = 22, bottom = 22;
  const ch = height - top - bottom;
  const all = [...points.flatMap((p) => [p.high, p.low]), ...forecast.flatMap((f) => [f.lower, f.upper])];
  let lo = Math.min(...all), hi = Math.max(...all);
  const pad = (hi - lo) * 0.08 || hi * 0.05;
  lo -= pad; hi += pad;
  // 예측 칸은 과거 칸의 1/3 넓이 (날짜 수와 상관없이)
  const plotW = Math.max(w - axisW, 10);
  const pastW = forecast.length ? plotW * 0.75 : plotW;
  const cw = pastW / Math.max(points.length, 1);
  const fw = forecast.length ? (plotW - pastW) / forecast.length : 0;
  const Y = (v) => top + ((hi - v) / (hi - lo)) * ch;
  const ticks = [0, 1, 2, 3, 4].map((k) => lo + ((hi - lo) * k) / 4);
  const labelEvery = Math.ceil(points.length / 6);
  const last = points.at(-1);
  const fx = (j) => pastW + (j + 0.5) * fw;

  return (
    <div ref={ref} className="candle">
      {w > 0 && (
        <svg width={w} height={height} role="img" aria-label="일별 가격 캔들 차트와 AI 예측">
          {ticks.map((v) => (
            <g key={v}>
              <line x1={0} x2={plotW} y1={Y(v)} y2={Y(v)} className="grid" />
              <text x={plotW + 6} y={Y(v) + 4} className="tick">{won(Math.round(v / 10) * 10)}</text>
            </g>
          ))}
          {points.map((p, i) => {
            const x = i * cw + cw / 2;
            const up = p.close >= p.open;
            const [y0, y1] = [Y(Math.max(p.open, p.close)), Y(Math.min(p.open, p.close))];
            return (
              <g key={p.date} className={up ? "up" : "dn"}>
                <title>{`${md(p.date)} 시가 ${won(p.open)} · 최고 ${won(p.high)} · 최저 ${won(p.low)} · 종가 ${won(p.close)}원`}</title>
                <line x1={x} x2={x} y1={Y(p.high)} y2={Y(p.low)} />
                <rect x={x - cw * 0.34} y={y0} width={Math.max(cw * 0.68, 1)} height={Math.max(y1 - y0, 1)} />
                {(i + Math.floor(labelEvery / 2)) % labelEvery === 0 && <text x={x} y={height - 6} className="tick mid">{md(p.date)}</text>}
              </g>
            );
          })}
          {forecast.length > 0 && last && (
            <g className="fc">
              <rect x={pastW} y={0} width={plotW - pastW} height={top + ch} className="fc-bg" />
              <line x1={pastW} x2={pastW} y1={0} y2={top + ch} className="fc-div" />
              <text x={pastW + 6} y={14} className="tick fc-t">AI 예측 →</text>
              <polygon
                className="fc-band"
                points={[
                  `${pastW},${Y(last.close)}`,
                  ...forecast.map((f, j) => `${fx(j)},${Y(f.upper)}`),
                  ...forecast.map((f, j) => `${fx(j)},${Y(f.lower)}`).reverse(),
                ].join(" ")}
              />
              <polyline className="fc-line" points={[`${pastW},${Y(last.close)}`, ...forecast.map((f, j) => `${fx(j)},${Y(f.price)}`)].join(" ")} />
              <text x={plotW - 2} y={height - 6} className="tick end">{md(forecast.at(-1).date)}</text>
            </g>
          )}
        </svg>
      )}
    </div>
  );
}

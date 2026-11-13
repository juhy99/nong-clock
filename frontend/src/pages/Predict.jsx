import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { getItems, predict } from "../api/ml";
import { getMarkets } from "../api/market";
import { Async, useAsync, useNarrow } from "../components/common";
import PredictSearch, { marketsIn, regionsOf } from "../components/PredictSearch";
import SeasonCharts from "../components/SeasonCharts";
import { ITEMS50, itemOf, varietyFactor, varietyOf } from "../mocks/items50";
import { LOW_ACCURACY } from "../mocks/accuracy";
import { addDays, daysBetween, md, todayIso, won } from "../utils/format";
import "./predict.css";

/* ─────────────────────────────────────────────
   AI 가격 예측 [샘플 11-11: 지역별 · 1년]
   조건: 지역(시·도) → 부류 → 품목 → 품종 → 예측 날짜(내일 ~ 1년 뒤, 빠른 버튼 1주·1개월·6개월·1년)
   그래프: 지역 안 도매시장마다 선 하나 (지난 8주 실제 + 예측 날짜까지 주 단위). 시장이 하나면 예측 범위 띠도
   오른쪽 "시장별 예측" 카드는 시장마다 한 장씩, 옆으로 밀어서(또는 ◀ ▶) 넘김. 2개월까지는 주별, 그보다 길면 달별
   ───────────────────────────────────────────── */
const DEFAULT_REGION = "서울";
const WEEKS_BACK = 8;
const COLORS = ["#e08a00", "#2f6fe4", "#2b8a57", "#b5478f"]; // 시장 순서대로 (한 지역 최대 4곳)

const pct = (v, base) => ((v - base) / base) * 100;
const signPct = (v) => `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(1)}%`;
const weekOfMonth = (iso) => `${Number(iso.slice(5, 7))}월 ${Math.ceil(Number(iso.slice(8, 10)) / 7)}주차`;
const marketLabel = (n) => (n === "전국 평균" || n === "전국 도매시장 평균" ? "전국 도매시장" : n);
/** 며칠 뒤 → "3주 뒤" / "5개월 뒤" */
const afterLabel = (t) => (t < 60 ? `${Math.round(t / 7)}주 뒤` : `${Math.round(t / 30.4)}개월 뒤`);

/** 예측에서 기준일 t일 뒤 값. DB 예측기는 출하철 밖 날을 빼고 주므로(11-11) 순서가 아니라 날짜로 찾는다 */
function fcAt(p, t) {
  p._fc ??= new Map(p.forecast.map((f) => [f.date, f]));
  const f = p._fc.get(addDays(p.base_date, t));
  return f ? { ...f, t } : null;
}
/** 고른 날들에 예측이 하나도 없으면 마지막 예측 하나라도 (기간 중간에 예측 없는 달이 있을 때) */
const orLast = (rows, p) => (rows.length || !p.forecast.length ? rows : [{ ...p.forecast.at(-1), t: daysBetween(p.base_date, p.forecast.at(-1).date) }]);

/** 한 시장 응답 → 주 단위 점: 지난 8주(기준일 포함) · 예측(7일마다, 마지막 날 포함) */
function weekly(p, horizon) {
  const byDate = new Map(p.history.map((h) => [h.date, h.price]));
  const past = Array.from({ length: WEEKS_BACK }, (_, i) => {
    const d = addDays(p.base_date, -7 * (WEEKS_BACK - 1 - i));
    return { date: d, price: byDate.get(d) ?? null };
  }).filter((x) => x.price != null);
  const ts = [];
  for (let t = 7; t < horizon; t += 7) ts.push(t);
  ts.push(horizon);
  const fut = orLast(ts.map((t) => fcAt(p, t)).filter((x) => x?.price != null), p);
  return { past, fut };
}

/** 표에 보여 줄 기간: 2개월까지는 주마다, 그보다 길면 한 달(30일)마다 + 마지막 날 */
function checkpoints(p, horizon) {
  const step = horizon <= 60 ? 7 : 30;
  const ts = [];
  for (let t = step; t < horizon; t += step) ts.push(t);
  if (!ts.length || horizon - ts[ts.length - 1] >= step / 2) ts.push(horizon);
  else ts[ts.length - 1] = horizon;
  return orLast(ts.map((t) => fcAt(p, t)).filter(Boolean), p).map((x) => ({ ...x, from: addDays(x.date, -(Math.min(step, x.t) - 1)) }));
}

/** 그래프: 시장마다 선 (지난 8주 얇게 → 예측 굵게). 시장 하나면 예측 범위 띠 */
/** 그래프 칸 크기 (넓은 화면은 카드가 오른쪽 열 높이만큼 늘어나고, 그래프가 남는 높이를 채움) */
function useBox() {
  const ref = useRef(null);
  const [box, setBox] = useState(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof ResizeObserver === "undefined") return undefined;
    const ro = new ResizeObserver(([e]) => setBox({ w: e.contentRect.width, h: e.contentRect.height }));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, box];
}

function Chart({ series, horizon }) {
  const narrow = useNarrow();
  const [boxRef, box] = useBox();
  const W = narrow ? 420 : 900;
  // 칸의 가로세로 비율대로 그림 높이를 정함 (글씨 크기는 그대로, 세로로 늘어남)
  const H = box?.w ? Math.max(narrow ? 340 : 300, Math.min(narrow ? 520 : 560, Math.round((box.h / box.w) * W))) : narrow ? 380 : 360;
  const L = narrow ? 52 : 64, R = narrow ? 14 : 24, T = 30, B = 40;
  const one = series.length === 1 ? series[0] : null;
  const all = [...series[0].past, ...series[0].fut]; // x 축 = 첫 시장 기준 (시장마다 날짜는 같음)
  const k = series[0].past.length - 1;
  const vals = series.flatMap((s) => [...s.past.map((x) => x.price), ...s.fut.map((x) => x.price)])
    .concat(one ? one.fut.flatMap((f) => [f.lower, f.upper]) : []);
  const step = (() => { const r = Math.max(...vals) - Math.min(...vals) || 100; return [10, 20, 50, 100, 200, 500, 1000, 2000, 5000].find((s) => r / s <= 6) ?? 10000; })();
  const lo = Math.floor(Math.min(...vals) / step) * step, hi = Math.ceil(Math.max(...vals) / step) * step;
  // x 는 날짜 비례 (지난 8주와 1년 뒤가 같은 그림에 들어가게)
  const d0 = all[0].date, span = Math.max(1, daysBetween(d0, all[all.length - 1].date));
  const X = (iso) => L + (daysBetween(d0, iso) * (W - L - R)) / span;
  const Y = (v) => T + ((hi - v) / (hi - lo || 1)) * (H - T - B);
  const now = all[k].date;
  const ticks = [];
  for (let v = lo; v <= hi; v += step) ticks.push(v);
  // 날짜 이름표: 처음 · 지금 · 끝 + 사이에 몇 개 (예측 기간에 따라 주/달)
  const fLabels = (() => {
    const out = [[all[0].date, md(all[0].date)], [now, "지금"], [all[all.length - 1].date, afterLabel(horizon)]];
    const n = narrow ? 1 : horizon <= 60 ? 3 : 4;
    for (let i = 1; i <= n; i++) {
      const t = Math.round((horizon * i) / (n + 1));
      if (t > 3 && horizon - t > (horizon <= 60 ? 6 : 25)) out.push([addDays(now, t), afterLabel(t)]);
    }
    return out;
  })();
  const pts = (arr) => arr.map((x) => `${X(x.date)},${Y(x.price)}`).join(" ");
  return (
    <div className="pv-chartbox" ref={boxRef}>
    <svg className="pv-chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`지난 8주 실제 가격과 ${afterLabel(horizon)}까지 예측, 시장별`}>
      {ticks.map((v) => (
        <g key={v}>
          <line x1={L} x2={W - R} y1={Y(v)} y2={Y(v)} stroke="rgba(19,38,26,.08)" />
          <text x={L - 10} y={Y(v) + 5} textAnchor="end" fontSize="15" fill="rgba(19,38,26,.8)">{won(v)}</text>
        </g>
      ))}
      {fLabels.map(([d, t], i) => (
        <text key={i} x={X(d)} y={H - 10} textAnchor={i === 0 ? "start" : i === 2 ? "end" : "middle"} fontSize="15"
          fill={i === 1 ? "#13261a" : "rgba(19,38,26,.8)"} fontWeight={i === 1 ? 700 : 400}>{t}</text>
      ))}
      <rect x={X(now)} y={T - 14} width={W - R - X(now)} height={H - T - B + 14} fill="rgba(217,138,0,.05)" rx="8" />
      <line x1={X(now)} x2={X(now)} y1={T - 14} y2={H - B} stroke="rgba(19,38,26,.35)" strokeDasharray="4 4" />
      {one && (
        <polygon fill="rgba(20,96,59,.12)" points={[...[one.past[k], ...one.fut].map((f, i) => `${X(f.date)},${Y(i ? f.upper : f.price)}`),
          ...[one.past[k], ...one.fut].map((f, i) => `${X(f.date)},${Y(i ? f.lower : f.price)}`).reverse()].join(" ")} />
      )}
      {series.map((s) => (
        <g key={s.code}>
          <polyline className="pv-path" points={pts(s.past)} fill="none" stroke={s.color} strokeOpacity=".55" strokeWidth="2.5" strokeLinejoin="round" />
          <polyline className="pv-path" points={pts([s.past[s.past.length - 1], ...s.fut])} fill="none" stroke={s.color} strokeWidth="4" strokeLinejoin="round" />
          <circle cx={X(s.best.date)} cy={Y(s.best.price)} r="6.5" fill={s.color} stroke="#fff" strokeWidth="2.5" />
        </g>
      ))}
      <circle cx={X(now)} cy={Y(series[0].past[k].price)} r="4.5" fill="#13261a" />
    </svg>
    </div>
  );
}

/** 시장별 예측 카드: 시장마다 한 장, 옆으로 밀거나 ◀ ▶ 로 넘김 (scroll-snap) */
function MarketCards({ series, horizon }) {
  const track = useRef(null);
  const [at, setAt] = useState(0);
  const go = (i) => {
    const el = track.current;
    if (el) el.scrollTo({ left: i * el.clientWidth, behavior: "smooth" });
  };
  const onScroll = () => {
    const el = track.current;
    if (el) setAt(Math.round(el.scrollLeft / el.clientWidth));
  };
  const s = series[at] ?? series[0];
  return (
    <section className="card pv-mk">
      <div className="pv-head">
        <h2>{horizon <= 60 ? "주별" : "달별"} 예측</h2>
        {series.length > 1 ? (
          <div className="pv-nav">
            <button type="button" aria-label="이전 시장" disabled={at === 0} onClick={() => go(at - 1)}>‹</button>
            <span><i style={{ background: s.color }} />{s.name} <small>{at + 1}/{series.length}</small></span>
            <button type="button" aria-label="다음 시장" disabled={at === series.length - 1} onClick={() => go(at + 1)}>›</button>
          </div>
        ) : <small>{s.name} · 원/kg</small>}
      </div>
      <div className="pv-track" ref={track} onScroll={onScroll}>
        {series.map((m) => (
          <ul className="pv-weeks pv-slide" key={m.code} aria-label={`${m.name} 예측`}>
            <li className="now"><span className="w"><b>지금</b>{md(m.base_date)} 기준</span><span className="rg" /><span className="pr">{won(m.base)}원</span></li>
            {m.rows.map((f) => {
              const c = pct(f.price, m.base), best = f.t === m.bestRow.t && f.price > m.base; // 지금보다 비쌀 때만 출하 추천
              return (
                <li key={f.t} className={best ? "best" : ""}>
                  <span className="w"><b>{horizon <= 60 ? afterLabel(f.t) : `${Math.max(1, Math.round(f.t / 30.4))}개월 뒤`}{best && <em>출하 추천</em>}</b>{md(f.from)}~{md(f.date)}</span>
                  <span className="rg">범위 {won(f.lower)} ~ {won(f.upper)}원</span>
                  <span className="pr">{won(f.price)}원<small className={c >= 0 ? "up" : "down"}>{signPct(c)}</small></span>
                </li>
              );
            })}
          </ul>
        ))}
      </div>
      {series.length > 1 && (
        <div className="pv-dots">
          {series.map((m, i) => <button key={m.code} type="button" aria-label={`${m.name} 보기`} className={i === at ? "on" : ""} style={{ "--c": m.color }} onClick={() => go(i)} />)}
          <span>옆으로 밀어서 시장을 바꿔 보세요</span>
        </div>
      )}
    </section>
  );
}

function Result({ r }) {
  const { series, horizon, regionName, itemName, item, baseName } = r;
  if (!series.length) return <div className="card state">이 지역 도매시장에서는 이 품목을 거래하지 않아요. 다른 지역을 골라 주세요.</div>;
  const top = series.reduce((a, s) => (s.best.price > a.best.price ? s : a));
  const gain = top.best.price - top.base;
  const p = series[0].raw;
  const low = LOW_ACCURACY.has(item);
  const one = series.length === 1 ? series[0] : null;
  return (
    <div className="pv-grid">
      <section className="card pv-main">
        <div className="pv-head"><h2>{itemName} · {regionName}</h2><small>원/kg · 오늘부터 {afterLabel(horizon)}({md(addDays(series[0].base_date, horizon))})까지</small></div>
        <div className="pv-big">
          <b>{won(top.best.price)}원</b>
          <span className={gain >= 0 ? "up" : "down"}>{signPct(pct(top.best.price, top.base))}</span>
          <span className="muted">{series.length > 1 ? `${top.name} · ` : ""}{afterLabel(top.best.t)} 최고 예상가 · 지금 {won(top.base)}원</span>
          {low && <span className="pv-low">❗ 예측 정확도가 낮은 품목이에요</span>}
        </div>
        <Chart series={series} horizon={horizon} />
        <div className="pv-legend">
          {series.map((s) => <span key={s.code}><i style={{ background: s.color, height: 4 }} />{s.name}</span>)}
          <span><i style={{ background: "rgba(19,38,26,.35)" }} />옅은 선 = 지난 8주 실제</span>
          {one && <span><i style={{ background: "rgba(20,96,59,.25)", height: 10 }} />예측 범위</span>}
        </div>
        {series.length > 1 && (
          <div className="pv-cmp">
            {series.map((s) => (
              <span key={s.code} className={s === top ? "top" : ""}>
                <i style={{ background: s.color }} /><b>{s.name}</b> 지금 {won(s.base)}원 → 최고 <b>{won(s.best.price)}원</b> ({afterLabel(s.best.t)})
              </span>
            ))}
          </div>
        )}
        <div className="pv-verdict">
          <span className="ic" aria-hidden>📅</span>
          <div>
            {gain > 0
              ? <b>출하 추천: <em>{series.length > 1 ? `${top.name} · ` : ""}{weekOfMonth(top.best.date)}</em> ({md(top.best.date)} 무렵)</b>
              : <b>출하 추천: <em>지금</em> ({md(top.base_date)})</b>}
            <p>{gain > 0 ? <>지금 {top.name} 시세보다 kg당 약 <b>{won(gain)}원</b> 더 받을 수 있어요.</> : <>앞으로 {afterLabel(horizon)}까지는 지금보다 낮을 것으로 보여요. 지금 파는 편이 나아요.</>}</p>
          </div>
        </div>
      </section>
      <div className="pv-side">
        <MarketCards series={series} horizon={horizon} />
        <section className="card">
          <div className="pv-head"><h2>이 예측, 믿을 만한가요?</h2></div>
          <div className="pv-acc">
            <div className="pv-ring" style={{ "--v": p.confidence }}><span>{p.confidence}%</span></div>
            <p>지난 검증 기간에 이 품목 {afterLabel(horizon)} 예측은<br />실제 가격과 평균 <b>±{Math.round(p.error_pct)}% 안</b>에서 맞았어요.</p>
          </div>
          {/* 이상기후 주의 구간은 실제 모델이 붙을 때까지 숨김 (11-13, 지금 ml-api 값은 더미) */}
          {p.reference === "baseline" && (
            <ul className="pv-notes"><li><span className="ic">🔖</span>이 품목·기간은 예측이 덜 정확해 참고용이에요</li></ul>
          )}
        </section>
      </div>
      {/* 계절 패턴 · 월별 반입량 (품목 단위, 전국) — 예시 데이터는 지금 시세 평균에 맞춰 크기 조정 */}
      <div className="pv-wide"><SeasonCharts item={item} itemName={baseName} anchor={Math.round(series.reduce((a, s) => a + s.base, 0) / series.length)} /></div>
    </div>
  );
}

export default function Predict() {
  const [params, setParams] = useSearchParams();
  const options = useAsync(async () => {
    const [items, markets] = await Promise.all([getItems(), getMarkets()]);
    return { items, markets };
  });
  const opts = options.data;
  const today = todayIso();
  const pTo = params.get("to");
  const regionOk = (r) => !!opts && regionsOf(opts.markets).some((x) => x.code === r);
  // 옛 주소(?market=110001)는 그 시장의 시·도로
  const oldMarket = opts?.markets.find((m) => m.code === params.get("market"));
  const fromMarket = oldMarket ? (oldMarket.code === "national" ? "national" : oldMarket.sido) : null;
  const q = {
    region: regionOk(params.get("region")) ? params.get("region") : regionOk(fromMarket) ? fromMarket : DEFAULT_REGION,
    item: itemOf(params.get("item"))?.code ?? ITEMS50[0].code,
    variety: varietyOf(itemOf(params.get("item"))?.code, params.get("variety")) ? params.get("variety") : "",
    to: pTo && daysBetween(today, pTo) >= 1 && daysBetween(today, pTo) <= 365 ? pTo : addDays(today, 30),
  };
  const horizon = daysBetween(today, q.to);
  const variety = varietyOf(q.item, q.variety);
  const result = useAsync(async () => {
    if (!opts) return null;
    const ms = marketsIn(opts.markets, q.region, q.item);
    // 품종: DB 예측기는 품종 예측을 그대로 돌려줌(raw.variety). 더미(raw.variety 빈 값)면 [샘플] 품목 예측 × 품종 계수
    const res = await Promise.all(ms.map((m) => predict({ item: q.item, market: m.code, horizon, history_days: 56, ...(q.variety ? { variety: q.variety } : {}) })));
    const series = res.map((raw, i) => {
      const f = (raw.variety ?? "") === q.variety ? 1 : varietyFactor(q.variety || null);
      const k = (v) => Math.round(v * f);
      const p = {
        ...raw, base_price: k(raw.base_price),
        history: raw.history.map((h) => ({ ...h, price: k(h.price) })),
        forecast: raw.forecast.map((x) => ({ ...x, price: k(x.price), lower: k(x.lower), upper: k(x.upper) })),
      };
      const w = weekly(p, horizon);
      const rows = checkpoints(p, horizon);
      const best = w.fut.reduce((a, x) => (x.price > a.price ? x : a));
      const bestRow = rows.reduce((a, x) => (x.price > a.price ? x : a));
      return { code: ms[i].code, name: marketLabel(raw.market_name ?? ms[i].name), color: COLORS[i % COLORS.length], base: p.base_price, base_date: p.base_date, ...w, rows, best, bestRow, raw: p };
    });
    const regionName = q.region === "national" ? "전국 도매시장" : `${q.region} 도매시장 ${ms.length}곳`;
    const itemName = (res[0]?.item_name ?? itemOf(q.item)?.name) + (variety ? ` ${variety.label}` : "");
    return { series, horizon, regionName, itemName, item: q.item, baseName: res[0]?.item_name ?? itemOf(q.item)?.name ?? "" };
  }, [!!opts, q.region, q.item, q.variety, q.to]);
  const search = (d) => setParams({ item: d.item, ...(d.variety ? { variety: d.variety } : {}), region: d.region, to: d.to }, { replace: true });

  return (
    <div className="page">
      <div className="page-head">
        <h1>언제, 어디에 팔면 가장 비쌀까</h1>
        <p>지역 · 품목과 예측 날짜를 고르면, 지역 안 도매시장마다 앞으로의 가격을 알려 드려요 (최대 1년).</p>
      </div>
      <Async state={options}>
        {(o) => (
          <>
            <PredictSearch key={JSON.stringify(q)} value={q} markets={o.markets} today={today} onSearch={search} />
            <Async state={result} minHeight={420}>{(r) => <Result r={r} />}</Async>
          </>
        )}
      </Async>
    </div>
  );
}

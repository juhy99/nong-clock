import { useSearchParams } from "react-router-dom";
import { getItems, predict } from "../api/ml";
import { getMarkets } from "../api/market";
import { Async, useAsync, useNarrow } from "../components/common";
import PredictSearch from "../components/PredictSearch";
import { ITEMS50, itemOf, varietyFactor, varietyOf } from "../mocks/items50";
import { LOW_ACCURACY } from "../mocks/accuracy";
import { addDays, daysBetween, md, todayIso, won } from "../utils/format";
import "./predict.css";

/* ─────────────────────────────────────────────
   AI 가격 예측 (v17, 11-11)
   조건: 도매시장 → 부류 → 품목 → 품종 → 기준 날짜. 기준일부터 4주(horizon 28)를 예측하고,
   그래프는 기준일 앞 8주 실제(history_days 56) + 앞으로 4주 예측 + 작년 같은 시기(last_year) 를 주 단위로 그림
   ───────────────────────────────────────────── */
const DEFAULT_MARKET = "110001"; // 서울가락
const WEEKS_BACK = 8;
const LY_DAYS = 364; // 작년 같은 시기 = 52주 전 같은 요일 (ml-api 와 같음)

const pct = (v, base) => ((v - base) / base) * 100;
const signPct = (v) => `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(1)}%`;
/** 날짜 → "11월 4주차" (그 달의 몇째 주) */
const weekOfMonth = (iso) => `${Number(iso.slice(5, 7))}월 ${Math.ceil(Number(iso.slice(8, 10)) / 7)}주차`;

/** 응답을 주 단위로: 과거 8점(기준일 포함) · 앞으로 4점 · 작년 같은 자리 12점 */
function weekly(p) {
  const byDate = new Map(p.history.map((h) => [h.date, h.price]));
  const past = Array.from({ length: WEEKS_BACK }, (_, i) => {
    const d = addDays(p.base_date, -7 * (WEEKS_BACK - 1 - i));
    return { date: d, price: byDate.get(d) ?? null };
  }).filter((x) => x.price != null);
  const fut = [7, 14, 21, 28].map((t) => p.forecast[t - 1]).filter(Boolean);
  const lyBy = new Map((p.last_year ?? []).map((h) => [addDays(h.date, LY_DAYS), h.price]));
  const ly = [...past, ...fut].map((x) => lyBy.get(x.date) ?? null);
  return { past, fut, ly };
}

/** 그래프: 올해 실제(진한 초록) · AI 예측(주황) + 범위 · 작년 같은 시기(파랑) */
function Chart({ past, fut, ly }) {
  // 휴대폰: 좁은 그림으로 다시 그려 글씨가 작아지지 않게 (날짜 이름표는 몇 개만)
  const narrow = useNarrow();
  const W = narrow ? 420 : 900, H = narrow ? 380 : 340, L = narrow ? 52 : 64, R = narrow ? 14 : 24, T = 40, B = 40;
  const all = [...past, ...fut];
  const vals = [...all.map((x) => x.price), ...fut.flatMap((f) => [f.lower, f.upper]), ...ly.filter((v) => v != null)];
  const step = (() => { const r = Math.max(...vals) - Math.min(...vals) || 100; return [10, 20, 50, 100, 200, 500, 1000, 2000, 5000].find((s) => r / s <= 6) ?? 10000; })();
  const lo = Math.floor(Math.min(...vals) / step) * step, hi = Math.ceil(Math.max(...vals) / step) * step;
  const X = (i) => L + (i * (W - L - R)) / Math.max(1, all.length - 1);
  const Y = (v) => T + ((hi - v) / (hi - lo || 1)) * (H - T - B);
  const k = past.length - 1;
  const fu = [past[k], ...fut];
  const top = Math.max(...fut.map((f) => f.price));
  const bi = past.length + fut.findIndex((f) => f.price === top);
  const lyPts = ly.map((v, i) => (v == null ? null : [X(i), Y(v)])).filter(Boolean);
  const lyTopV = Math.max(...ly.filter((v) => v != null));
  const lyTopI = ly.indexOf(lyTopV);
  const band = [...fu.map((f, i) => `${X(k + i)},${Y(i ? f.upper : f.price)}`), ...fu.map((f, i) => `${X(k + i)},${Y(i ? f.lower : f.price)}`).reverse()].join(" ");
  const labels = all.map((x, i) => (i < k ? md(x.date) : i === k ? "기준일" : `${i - k}주 뒤`))
    .map((t, i) => (!narrow || i === 0 || i === k || i === all.length - 1 || i === Math.round(k / 2) ? t : ""));
  // 이름표가 그래프 밖으로 잘리지 않게 x 를 안쪽으로
  const inX = (x, w) => Math.min(Math.max(x, L + w / 2), W - R - w / 2);
  const ticks = [];
  for (let v = lo; v <= hi; v += step) ticks.push(v);
  return (
    <svg className="pv-chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="지난 8주 실제 가격, 앞으로 4주 예측, 작년 같은 시기 가격">
      {ticks.map((v) => (
        <g key={v}>
          <line x1={L} x2={W - R} y1={Y(v)} y2={Y(v)} stroke="rgba(19,38,26,.08)" />
          <text x={L - 10} y={Y(v) + 5} textAnchor="end" fontSize="15" fill="rgba(19,38,26,.8)">{won(v)}</text>
        </g>
      ))}
      {labels.map((t, i) => (
        <text key={i} x={X(i)} y={H - 10} textAnchor={narrow && i === all.length - 1 ? "end" : narrow && i === 0 ? "start" : "middle"} fontSize="15" fill={i === k ? "#13261a" : "rgba(19,38,26,.8)"} fontWeight={i === k ? 700 : 400}>{t}</text>
      ))}
      <rect x={X(k)} y={T - 16} width={W - R - X(k)} height={H - T - B + 16} fill="rgba(217,138,0,.06)" rx="8" />
      <line x1={X(k)} x2={X(k)} y1={T - 16} y2={H - B} stroke="rgba(19,38,26,.35)" strokeDasharray="4 4" />
      <polygon points={band} fill="rgba(20,96,59,.12)" />
      {lyPts.length > 1 && (
        <>
          <polyline points={lyPts.map((p) => p.join(",")).join(" ")} fill="none" stroke="#4a6fb5" strokeWidth="2.5" strokeLinejoin="round" />
          {lyPts.map(([x, y], i) => <circle key={i} cx={x} cy={y} r="3" fill="#fff" stroke="#4a6fb5" strokeWidth="2" />)}
          <text x={lyPts[0][0] + 6} y={lyPts[0][1] - 10} fontSize="15" fontWeight="700" fill="#4a6fb5">작년</text>
          <g>
            <rect x={inX(X(lyTopI), narrow ? 150 : 210) - (narrow ? 75 : 105)} y={Y(lyTopV) - 46} width={narrow ? 150 : 210} height="30" rx="15" fill="#4a6fb5" />
            <text x={inX(X(lyTopI), narrow ? 150 : 210)} y={Y(lyTopV) - 25} textAnchor="middle" fontSize="15" fontWeight="700" fill="#fff">작년 최고 {won(lyTopV)}원{narrow ? "" : ` (${md(addDays(all[lyTopI].date, -LY_DAYS))})`}</text>
          </g>
        </>
      )}
      <polyline className="pv-path" points={past.map((x, i) => `${X(i)},${Y(x.price)}`).join(" ")} fill="none" stroke="rgba(19,38,26,.8)" strokeWidth="3" strokeLinejoin="round" />
      <text x={X(0) + 6} y={Y(past[0].price) + 24} fontSize="15" fontWeight="700" fill="#13261a">올해</text>
      <polyline className="pv-path" points={fu.map((x, i) => `${X(k + i)},${Y(x.price)}`).join(" ")} fill="none" stroke="#e08a00" strokeWidth="4" strokeLinejoin="round" />
      {fut.map((f, i) => (
        <circle key={f.date} cx={X(k + 1 + i)} cy={Y(f.price)} r={k + 1 + i === bi ? 8 : 4.5} fill={k + 1 + i === bi ? "#d92d20" : "#e08a00"} stroke="#fff" strokeWidth={k + 1 + i === bi ? 2.5 : 0} />
      ))}
      <circle cx={X(k)} cy={Y(past[k].price)} r="5" fill="#13261a" />
      <g>
        <rect x={inX(X(bi), 170) - 85} y={Y(top) + 16} width="170" height="30" rx="15" fill="#d92d20" />
        <text x={inX(X(bi), 170)} y={Y(top) + 37} textAnchor="middle" fontSize="15" fontWeight="800" fill="#fff">올해 예측 {won(top)}원</text>
      </g>
    </svg>
  );
}

function Result({ p }) {
  const { past, fut, ly } = weekly(p);
  if (!past.length || fut.length < 4) return <div className="card state">예측 값을 불러오지 못했어요.</div>;
  const base = p.base_price;
  const top = Math.max(...fut.map((f) => f.price));
  const wi = fut.findIndex((f) => f.price === top);
  const best = fut[wi];
  const gain = top - base;
  const lyNow = ly[past.length - 1];
  const lyTop = Math.max(...ly.filter((v) => v != null));
  const lyTopI = ly.indexOf(lyTop) - (past.length - 1);
  const low = LOW_ACCURACY.has(p.item);
  const marketName = p.market_name === "전국 평균" ? "전국 도매시장" : p.market_name;
  return (
    <div className="pv-grid">
      <section className="card pv-main">
        <div className="pv-head"><h2>{p.item_name} · {marketName}</h2><small>원/kg · {p.base_date.replaceAll("-", ". ")}. 기준</small></div>
        <div className="pv-big">
          <b>{won(top)}원</b>
          <span className={gain >= 0 ? "up" : "down"}>{signPct(pct(top, base))}</span>
          <span className="muted">4주 안 최고 예상가 · 기준일 {won(base)}원</span>
          {low && <span className="pv-low">❗ 예측 정확도가 낮은 품목이에요</span>}
        </div>
        <Chart past={past} fut={fut} ly={ly} />
        <div className="pv-legend">
          <span><i style={{ background: "rgba(19,38,26,.75)" }} />지난 8주 실제 가격</span>
          <span><i style={{ background: "#e08a00" }} />AI 예측</span>
          <span><i style={{ background: "rgba(20,96,59,.25)", height: 10 }} />예측 범위</span>
          {lyNow != null && <span><i style={{ background: "#4a6fb5" }} />작년 같은 시기 (실제)</span>}
        </div>
        {lyNow != null && (
          <div className="pv-ly">
            <span>📅 작년 같은 주 <b>{won(lyNow)}원</b> → 올해 {won(base)}원 (<b>{signPct(pct(base, lyNow))}</b>)</span>
            <span>작년엔 <b>{lyTopI > 0 ? `${lyTopI}주 뒤` : lyTopI === 0 ? "기준일" : `${-lyTopI}주 전`} {won(lyTop)}원</b>이 가장 높았어요 · 올해 예측 최고는 {wi + 1}주 뒤</span>
          </div>
        )}
        <div className="pv-verdict">
          <span className="ic" aria-hidden>📅</span>
          <div>
            <b>출하 추천 시기: <em>{weekOfMonth(best.date)}</em> ({md(addDays(best.date, -6))} ~ {md(best.date)})</b>
            <p>{gain > 0 ? <>기준일에 파는 것보다 kg당 약 <b>{won(gain)}원</b> 더 받을 수 있어요.</> : <>앞으로 4주는 기준일보다 낮을 것으로 보여요. 기준일 무렵에 파는 편이 나아요.</>}</p>
          </div>
        </div>
      </section>
      <div className="pv-side">
        <section className="card">
          <div className="pv-head"><h2>주별 예측</h2><small>원/kg</small></div>
          <ul className="pv-weeks">
            {fut.map((f, i) => {
              const c = pct(f.price, base);
              return (
                <li key={f.date} className={i === wi ? "best" : ""}>
                  <span className="w"><b>{i + 1}주 뒤{i === wi && <em>출하 추천</em>}</b>{md(addDays(f.date, -6))}~{md(f.date)}</span>
                  <span className="rg">범위 {won(f.lower)} ~ {won(f.upper)}원</span>
                  <span className="pr">{won(f.price)}원<small className={c >= 0 ? "up" : "down"}>{signPct(c)}</small></span>
                </li>
              );
            })}
          </ul>
        </section>
        <section className="card">
          <div className="pv-head"><h2>이 예측, 믿을 만한가요?</h2></div>
          <div className="pv-acc">
            <div className="pv-ring" style={{ "--v": p.confidence }}><span>{p.confidence}%</span></div>
            <p>지난 검증 기간에 이 품목 4주 예측은<br />실제 가격과 평균 <b>±{Math.round(p.error_pct)}% 안</b>에서 맞았어요.</p>
          </div>
          <ul className="pv-notes">
            {p.alerts.map((a) => <li key={a.start}><span className="ic warn">⚠️</span>{md(a.start)}~{md(a.end)} 이상기후 주의 · 이 기간 예측은 참고만 하세요</li>)}
            {p.reference && <li><span className="ic">🔖</span>{p.reference === "far" ? "6개월보다 먼 예측이라 참고용이에요" : "이 품목·기간은 예측이 덜 정확해 참고용이에요"}</li>}
            {!p.alerts.length && !p.reference && <li><span className="ic ok">✓</span>이 기간에는 이상기후 주의 구간이 없어요</li>}
          </ul>
        </section>
      </div>
    </div>
  );
}

export default function Predict() {
  const [params, setParams] = useSearchParams();
  const options = useAsync(async () => {
    // 도매시장 목록은 시세 쪽(전국 평균 + 32곳, 시장마다 거래하는 품목 items)을 쓴다
    const [items, markets] = await Promise.all([getItems(), getMarkets()]);
    return { items, markets };
  });
  const opts = options.data;
  const today = todayIso();
  const pDate = params.get("date");
  const q = {
    item: itemOf(params.get("item"))?.code ?? ITEMS50[0].code,
    variety: varietyOf(itemOf(params.get("item"))?.code, params.get("variety")) ? params.get("variety") : "", // 없어진 품종 id(옛 주소)는 전체로
    market: params.get("market") || DEFAULT_MARKET,
    date: pDate && daysBetween(pDate, today) >= 0 && daysBetween(pDate, today) <= 365 ? pDate : today,
  };
  const variety = varietyOf(q.item, q.variety);
  const result = useAsync(async () => {
    if (!opts) return null;
    const p = await predict({ item: q.item, market: q.market, horizon: 28, history_days: 56, last_year: true, ...(q.date !== today ? { base_date: q.date } : {}) });
    // [샘플] 품종 가격 = 품목 예측 × 품종 계수 (품종별 모델이 붙으면 API 가 품종 값을 바로 준다)
    const f = varietyFactor(q.variety || null);
    const k = (v) => Math.round(v * f);
    return {
      ...p, item_name: variety ? `${p.item_name} ${variety.label}` : p.item_name,
      base_price: k(p.base_price), predicted_price: k(p.predicted_price),
      history: p.history.map((h) => ({ ...h, price: k(h.price) })),
      last_year: (p.last_year ?? []).map((h) => ({ ...h, price: k(h.price) })),
      forecast: p.forecast.map((x) => ({ ...x, price: k(x.price), lower: k(x.lower), upper: k(x.upper) })),
    };
  }, [!!opts, q.item, q.variety, q.market, q.date]);
  const search = (d) => setParams({ item: d.item, ...(d.variety ? { variety: d.variety } : {}), market: d.market, ...(d.date !== today ? { date: d.date } : {}) }, { replace: true });

  return (
    <div className="page">
      <div className="page-head">
        <h1>언제 팔면 가장 비쌀까</h1>
        <p>도매시장 · 품목과 기준 날짜를 고르면, 그날부터 4주 동안의 가격을 알려 드려요.</p>
      </div>
      <Async state={options}>
        {(o) => (
          <>
            <PredictSearch key={JSON.stringify(q)} value={q} markets={o.markets} today={today} onSearch={search} />
            <Async state={result} minHeight={420}>{(p) => <Result p={p} />}</Async>
          </>
        )}
      </Async>
    </div>
  );
}

// 홈 대시보드 (주식 앱처럼): 가격 예측·작물 추천 카드 → 지수 카드 8개 → 품목 차트 + 품목 순위 → AI 상승·하락·관심 품목
// 색: 오르면 빨강(.up), 내리면 파랑(.down). 가격 = 전국 도매시장 · 상 등급 · 원/kg
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getTopMovers, predict, recommendCrops, recommendPlantingDates } from "../api/ml";
import { getMarketIndex, getPriceHistory } from "../api/market";
import { useAuth } from "../components/AuthContext";
import CandleChart from "../components/CandleChart";
import { Async, PctChange, useAsync } from "../components/common";
import ItemImage from "../components/ItemImage";
import { LOW_ACCURACY } from "../mocks/accuracy";
import { DEFAULT_FORM, formRequest } from "./Recommend";
import { shortDate, todayIso, won, wonPerKg } from "../utils/format";

const pctOf = (v, base) => Math.round(((v - base) / base) * 1000) / 10;
const Warn = ({ code }) => (LOW_ACCURACY.has(code) ? <span className="ip-warn" title="예측 정확도가 낮은 품목">!</span> : null);

/** 지난 가격(실선) + AI 예측(점선·띠) 작은 그래프 */
function MiniForecast({ p, days = 30, height = 96, best, tone = "up" }) {
  const w = 300;
  const hist = p.history.map((h) => h.price);
  const fc = p.forecast.slice(0, days);
  const all = [...hist, ...fc.flatMap((f) => [f.lower, f.upper]), best?.price ?? hist[0]];
  const lo = Math.min(...all), hi = Math.max(...all);
  const edge = tone === "down" ? Math.max(best?.price ?? 0, lo) : Math.min(best?.price ?? 0, hi);
  const n = hist.length + fc.length - 1;
  const X = (i) => (i * w) / n;
  const Y = (v) => 6 + ((hi - v) / (hi - lo || 1)) * (height - 12);
  const k = hist.length - 1;
  const f = (sel) => fc.map((x, j) => `${X(k + j + 1)},${Y(sel(x))}`);
  // 가장 비싼 날이 그래프 기간(30일) 안이면 그 자리, 밖이면 오른쪽 끝에 점
  const bi = best ? fc.findIndex((x) => x.date === best.date) : -1;
  const bx = bi >= 0 ? X(k + bi + 1) : w - 4, by = best ? Y(edge) : 0;
  return (
    <svg className={`mini-fc ${tone}`} viewBox={`0 0 ${w} ${height}`} preserveAspectRatio="none" role="img" aria-label="지난 가격과 AI 예측">
      <defs><clipPath id="mf-wipe"><rect className="wipe" x={X(k)} y={0} width={w - X(k)} height={height} /></clipPath></defs>
      <rect x={X(k)} y={0} width={w - X(k)} height={height} className="bg" />
      <polyline className="past" points={hist.map((v, i) => `${X(i)},${Y(v)}`).join(" ")} />
      <g clipPath="url(#mf-wipe)">
        <polygon className="band" points={[`${X(k)},${Y(hist[k])}`, ...f((x) => x.upper), ...f((x) => x.lower).reverse()].join(" ")} />
        <polyline className="pred" points={[`${X(k)},${Y(hist[k])}`, ...f((x) => x.price)].join(" ")} />
      </g>
      <line x1={X(k)} x2={X(k)} y1={0} y2={height} className="div" />
      <circle className="now" cx={X(k)} cy={Y(hist[k])} r="3.5" />
      {best && <><circle className="best-ring" cx={bx} cy={by} r="5" /><circle className="best-dot" cx={bx} cy={by} r="4" /></>}
    </svg>
  );
}

/** 맨 위: 가격 예측 · 작물 추천 */
// 가격 예측 카드가 5초마다 돌려 보여 주는 순서: [기간(일), 방향]
const PRICE_SLIDES = [[90, "up"], [90, "down"], [30, "up"], [30, "down"], [7, "up"], [7, "down"]];
const H_LABEL = { 7: "1주", 30: "1개월", 90: "3개월" };
const LAND_SLIDES = [["open", "노지"], ["house", "시설"], ["paddy", "논"], ["orchard", "과수원"]];
const ORCHARD = [["apple", "사과", "🍎"], ["pear", "배", "🍐"], ["peach", "복숭아", "🍑"]];
const ROTATE_MS = 5000;

/** 5초마다 다음 칸으로: 0.4초 동안 지금 내용이 흐려지며 빠지고 → 다음 내용이 떠오름 (마우스를 올리면 멈춤, "동작 줄이기" 설정이면 돌지 않음) */
const LEAVE_MS = 400;
function useRotate(n) {
  const [i, setIdx] = useState(0);
  const [leaving, setLeaving] = useState(false);
  const [hold, setHold] = useState(false);
  const go = (next) => {
    setLeaving(true);
    setTimeout(() => { setIdx(next); setLeaving(false); }, LEAVE_MS);
  };
  useEffect(() => {
    if (!n || hold || window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return undefined;
    const t = setInterval(() => go((i + 1) % n), ROTATE_MS);
    return () => clearInterval(t);
  }, [n, hold, i]);
  return { i: n ? i % n : 0, setI: (k) => k !== i && go(k), leaving, hold: { onMouseEnter: () => setHold(true), onMouseLeave: () => setHold(false) } };
}

function Dots({ n, i, setI }) {
  return (
    <span className="cf-dots" onClick={(e) => e.preventDefault()}>
      {Array.from({ length: n }, (_, k) => <button key={k} type="button" aria-label={`${k + 1}번째 보기`} className={k === i ? "on" : ""} onClick={() => setI(k)} />)}
    </span>
  );
}

/** 맨 위: 가격 예측 (1주·1개월·3개월 뒤 가장 오를·내릴 품목을 돌려 보여 줌) · 작물 추천 (노지·시설·논 마진률 순위를 돌려 보여 줌) */
export function CoreFeatures({ items }) {
  // 기간별 급등락 후보 (정확도가 낮거나 참고용인 품목은 빼고)
  const movers = useAsync(async () => {
    const [w, m, q] = await Promise.all([7, 30, 90].map((h) => getTopMovers({ horizon: h, limit: 50 })));
    return { 7: w, 30: m, 90: q };
  });
  const slides = movers.data
    ? PRICE_SLIDES.map(([h, dir]) => {
        const ok = movers.data[h].filter((x) => !LOW_ACCURACY.has(x.item) && !x.reference);
        const pick = [...ok].sort((a, b) => (dir === "up" ? b.change_pct - a.change_pct : a.change_pct - b.change_pct))[0];
        return pick && { h, dir, pick };
      }).filter(Boolean)
    : [];
  const pr = useRotate(slides.length);
  const cur = slides[pr.i];
  const preds = useAsync(async () => {
    const codes = [...new Set(slides.map((x) => x.pick.item))];
    const rows = await Promise.all(codes.map((c) => predict({ item: c, horizon: 90 })));
    return Object.fromEntries(codes.map((c, k) => [c, rows[k]]));
  }, [slides.map((x) => x.pick.item).join()]);
  const p = cur && preds.data?.[cur.pick.item];
  const at = (d) => p && pctOf(p.forecast[d - 1].price, p.base_price);
  const win = p?.forecast.slice(0, cur.h) ?? [];
  const mark = win.length ? win.reduce((a, f) => (cur.dir === "up" ? f.price > a.price : f.price < a.price) ? f : a) : null;
  const curPct = p && pctOf(p.forecast[cur.h - 1].price, p.base_price);

  // 작물 추천: 예시 땅(경기 · 노지·시설·논)으로 계산해서 토지별 마진률 순위.
  // 지금 심을 작물이 없는 토지(예: 11월의 논)는 다음 심는 날 기준으로 다시 계산
  const rec = useAsync(async () => {
    const today = todayIso();
    const form = { ...DEFAULT_FORM, lands: { open: 1200, house: 600, paddy: 1000, orchard: 0 } };
    const now = await recommendCrops(formRequest(form, today));
    const out = {};
    for (const [t] of LAND_SLIDES.slice(0, 3)) {
      const rows = now.results.filter((r) => !r.demoted && r.land_type === t);
      if (rows.length) { out[t] = { rows, from: null }; continue; }
      // 작물마다 자기 다음 심는 날로 계산 (쌀 5월 · 콩 6월 …)
      const wait = now.unavailable.filter((u) => u.land_type === t && u.next_plant_date);
      if (!wait.length) continue;
      // 작물 추천 API 는 시작일을 30일 안만 받으므로, 작물별 "가장 좋은 심는 날" API 로 1년 안 최적 날짜 결과를 받는다
      const area = form.lands[t];
      const later = await Promise.all(wait.map((u) => recommendPlantingDates({ crop: u.crop, area_pyeong: area, region: form.region }).catch(() => null)));
      const rowsLater = later.map((x) => x?.best).filter((r) => r && !r.demoted);
      if (rowsLater.length) out[t] = { rows: rowsLater, from: true };
    }
    // 과수원: 여러 해 기르는 나무라 마진 대신 수확철(가을) 예상 도매가
    const fr = await Promise.all(ORCHARD.map(([c]) => predict({ item: c, horizon: 365 }).catch(() => null)));
    out.orchard = {
      orchard: true,
      rows: ORCHARD.filter((_, k) => fr[k]).map(([c, name, emoji]) => {
        const k = ORCHARD.findIndex((o) => o[0] === c);
        const fall = fr[k].forecast.filter((f) => [9, 10, 11].includes(Number(f.date.slice(5, 7))));
        return { crop: c, crop_name: name, emoji, price: Math.round(fall.reduce((a, f) => a + f.price, 0) / (fall.length || 1)) };
      }).sort((a, b) => b.price - a.price),
    };
    return out;
  });
  const lands = LAND_SLIDES.map(([t, name]) => ({ t, name, ...(rec.data?.[t] ?? {}) }))
    .filter((l) => l.rows?.length)
    .map((l) => (l.orchard ? l : { ...l, rows: [...l.rows].sort((a, b) => b.margin_rate - a.margin_rate).slice(0, 3) }));
  const rr = useRotate(lands.length);
  const land = lands[rr.i];
  const maxPrice = land?.orchard ? Math.max(...land.rows.map((r) => r.price)) : 1;
  const maxRate = 80; // 막대 끝 = 마진률 80%

  return (
    <section className="core-feat">
      <Link to={cur ? `/ai?item=${cur.pick.item}&date=${p?.forecast[cur.h - 1].date ?? ""}` : "/ai"} className={`cf ai ${pr.leaving ? "leaving" : ""}`} {...pr.hold}>
        <div className="cf-main">
          <div className="cf-head"><span className="cf-tag">가격 예측</span></div>
          <h2>🤖 수확한 작물, <em>언제 팔까?</em></h2>
          {cur && p ? (
            <div className={`cf-live cf-swap ${cur.dir}`} key={pr.i}>
              <span className="muted small"><b className={`cf-when ${cur.dir}`}>{H_LABEL[cur.h]} 뒤</b> 가장 크게 {cur.dir === "up" ? "오를" : "내릴"} 품목</span>
              <b><ItemImage code={cur.pick.item} emoji={items?.find((i) => i.code === cur.pick.item)?.emoji} className="xs" /> {p.item_name} {won(p.forecast[cur.h - 1].price)}원 <PctChange value={curPct} /></b>
              <span className="muted small">지금 {wonPerKg(p.base_price)}</span>
            </div>
          ) : <span className="muted small">예측 불러오는 중…</span>}
          <Dots n={slides.length} i={pr.i} setI={pr.setI} />
        </div>
        {cur && p && mark && (
          <div className="cf-side cf-swap" key={`s${pr.i}`}>
            <div className="mini-fc-wrap">
              <MiniForecast p={p} days={cur.h} height={56} best={mark} tone={cur.dir} />
            </div>
            <div className={`cf-best ${cur.dir}`}>
              <span className="ic" aria-hidden>{cur.dir === "up" ? "💰" : "🧊"}</span>
              <div className="t"><small>{H_LABEL[cur.h]} 안 가장 {cur.dir === "up" ? "비싼" : "싼"} 날</small><b>{shortDate(mark.date)}</b></div>
              <div className="v"><b className="num">{won(mark.price)}원</b><PctChange value={pctOf(mark.price, p.base_price)} /></div>
            </div>
            <div className="cf-stats three">
              {[["1주 뒤", at(7), 7], ["1개월 뒤", at(30), 30], ["3개월 뒤", at(90), 90]].map(([t, v, d]) => (
                <div key={t} className={d === cur.h ? "on" : ""}><small>{t}</small><PctChange value={v} /></div>
              ))}
            </div>
          </div>
        )}
        <span className="cf-go">가격 예측 보러 가기 →</span>
      </Link>
      <Link to="/recommend" className={`cf rc ${rr.leaving ? "leaving" : ""}`} {...rr.hold}>
        <div className="cf-head"><span className="cf-tag">작물 추천</span></div>
        <h2>🌱 내 땅에는 <em>무엇을 심을까?</em></h2>
        {land ? (
          <>
            <div className="cf-land">
              {lands.map((l, k) => <span key={l.t} className={k === rr.i ? "on" : ""}>{l.name}</span>)}
              <small className="cf-swap" key={`l${rr.i}`}>{land.orchard ? "수확철 예상 도매가 · 나무 심고 3~5년 뒤부터" : land.from ? "마진률 높은 작물 · 다음 심는 때 기준" : "마진률 높은 작물"}</small>
            </div>
            <ol className="cf-crops">
              {[0, 1, 2].map((k) => {
                const c = land.rows[k];
                return (
                  <li key={k} style={{ "--i": k }} className={c ? "" : "empty"}>
                    <span className="n">{k + 1}</span>
                    <span className="e cf-swap" key={`e${rr.i}`}>{c?.emoji}</span>
                    <span className="nm cf-swap" key={`n${rr.i}`}>{c?.crop_name ?? "-"}{land.from && c ? <small>{shortDate(c.plant_date)} 심기</small> : null}</span>
                    <span className="bar"><i style={{ width: `${!c ? 0 : land.orchard ? (c.price / maxPrice) * 85 : Math.min(100, (c.margin_rate / maxRate) * 100)}%` }} /></span>
                    <span className="v cf-swap" key={`v${rr.i}`}>
                      {c && land.orchard ? <><b>{won(c.price)}원</b><small>/kg</small></> : <><b>{c ? `${Math.round(c.margin_rate)}%` : ""}</b><small>{c ? `${won(Math.round(c.margin / 1e4))}만원` : ""}</small></>}
                    </span>
                  </li>
                );
              })}
            </ol>
          </>
        ) : <span className="muted small">추천 불러오는 중…</span>}
        <Dots n={lands.length} i={rr.i} setI={rr.setI} />
        <span className="cf-go">내 땅으로 추천받기 →</span>
      </Link>
    </section>
  );
}

/** 지수 카드 작은 그래프: 지난 30거래일 + AI 30일 예상(점선) */
function IndexSpark({ points, forecastPct }) {
  const w = 150, h = 40;
  const vals = points.map((p) => p.value);
  const end = vals.at(-1) * (1 + forecastPct / 100);
  const lo = Math.min(...vals, end), hi = Math.max(...vals, end);
  const pastW = w * 0.72;
  const X = (i) => (i * pastW) / (vals.length - 1);
  const Y = (v) => 3 + ((hi - v) / (hi - lo || 1)) * (h - 6);
  return (
    <svg className="ix-spark" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" aria-hidden="true">
      <rect x={pastW} y={0} width={w - pastW} height={h} className="bg" />
      <polyline className={vals.at(-1) >= vals[0] ? "up" : "down"} points={vals.map((v, i) => `${X(i)},${Y(v)}`).join(" ")} />
      <polyline className="pred" points={`${pastW},${Y(vals.at(-1))} ${w},${Y(end)}`} />
    </svg>
  );
}

/** 지수 카드 8개: 전체 + 7묶음 (평소 가격 = 100) · 아래 줄 = AI 30일 뒤 예상 등락률 (묶음 품목 평균) */
export function IndexCards({ movers, items }) {
  const state = useAsync(() => getMarketIndex({ days: 30 }));
  const cat = Object.fromEntries((items ?? []).map((i) => [i.code, i.category]));
  const forecastOf = (g) => {
    const rows = (movers ?? []).filter((m) => !g.categories || g.categories.includes(cat[m.item]));
    return rows.length ? Math.round((rows.reduce((a, m) => a + m.change_pct, 0) / rows.length) * 10) / 10 : null;
  };
  return (
    <section>
      <Async state={state} minHeight={150}>
        {(d) => (
          <>
            <div className="ix-row">
              {d.groups.map((g) => {
                const f = forecastOf(g);
                const pct = g.change_pct;
                const dir = Math.abs(pct) < 0.05 ? "flat" : pct > 0 ? "up" : "down";
                return (
                  <Link key={g.code} to="/market" className="ix">
                    <div className="ix-h">{g.emoji} {g.name}</div>
                    <small className="ix-l">어제보다</small>
                    <b className={`num ${dir}`}>{dir === "flat" ? "– 0.0%" : `${pct > 0 ? "▲" : "▼"} ${Math.abs(pct).toFixed(1)}%`}</b>
                    <IndexSpark points={g.points} forecastPct={f ?? 0} />
                    {f != null && (
                      <div className="ix-f">AI 30일 뒤 <b className={f > 0 ? "up" : f < 0 ? "down" : ""}>{f > 0 ? "▲" : f < 0 ? "▼" : "–"} {Math.abs(f).toFixed(1)}% {f > 0 ? "상승" : f < 0 ? "하락" : "보합"}</b></div>
                    )}
                  </Link>
                );
              })}
            </div>
          </>
        )}
      </Async>
    </section>
  );
}

const RANGES = [{ label: "1주", days: 5 }, { label: "1개월", days: 22 }, { label: "3개월", days: 66 }, { label: "1년", days: 250 }];
const TABS = [
  { key: "vol", label: "거래량 많은" },
  { key: "up", label: "많이 오른" },
  { key: "down", label: "많이 내린" },
  { key: "ai_up", label: "AI 상승 예상" },
  { key: "ai_down", label: "AI 하락 예상" },
];

/** 순위 한 줄 */
function Row({ n, code, emoji, name, sub, price, pct, on, onClick, to, star, onStar }) {
  const body = (
    <>
      <span className="n">{n}</span>
      <ItemImage code={code} emoji={emoji} className="xs" />
      <span className="nm">{name}<Warn code={code} />{sub && <small>{sub}</small>}</span>
      <span className="pr"><b>{won(price)}원</b><PctChange value={pct} className="small" /></span>
      {star && <button type="button" className="star" title="관심 품목에 담기" onClick={(e) => { e.preventDefault(); e.stopPropagation(); onStar(); }}>☆</button>}
    </>
  );
  if (to) return <li><Link className="db-row" to={to}>{body}</Link></li>;
  return <li><button type="button" className={`db-row ${on ? "on" : ""}`} onClick={onClick}>{body}</button></li>;
}

/** 품목 차트(캔들 + AI 30일) + 실시간 품목 순위 */
export function MarketBoard({ today, movers, items }) {
  const { user } = useAuth();
  const [picked, setPicked] = useState(null);
  const [range, setRange] = useState(66);
  const [tab, setTab] = useState("vol");
  const item = picked ?? user?.favorites?.[0] ?? "apple";
  const info = Object.fromEntries((items ?? []).map((i) => [i.code, i]));
  const hist = useAsync(() => getPriceHistory(item, { days: range }), [item, range]);
  const pred = useAsync(() => predict({ item, horizon: 30 }), [item]);
  const row = today?.items.find((p) => p.item === item);
  const ai = Object.fromEntries((movers ?? []).map((m) => [m.item, m]));

  const prices = today?.items ?? [];
  const list = {
    vol: prices, // 오늘 시세 순서 = 거래 물량 많은 순
    up: [...prices].sort((a, b) => b.change_pct - a.change_pct),
    down: [...prices].sort((a, b) => a.change_pct - b.change_pct),
    ai_up: [...prices].filter((p) => ai[p.item]).sort((a, b) => ai[b.item].change_pct - ai[a.item].change_pct),
    ai_down: [...prices].filter((p) => ai[p.item]).sort((a, b) => ai[a.item].change_pct - ai[b.item].change_pct),
  }[tab].slice(0, 8);
  const isAi = tab.startsWith("ai");

  const candles = (hist.data?.points ?? [])
    .map((p, i, arr) => {
      if (p.price == null) return null;
      const open = arr[i - 1]?.price ?? p.price;
      return { date: p.date, open, close: p.price, high: Math.max(p.high, open, p.price), low: Math.min(p.low, open, p.price) };
    })
    .filter(Boolean);
  const p = pred.data;
  const low = LOW_ACCURACY.has(item);

  return (
    <div className="db-board">
      <section className="card db-chart">
        <div className="db-chart-head">
          <span className="db-emo"><ItemImage code={item} emoji={info[item]?.emoji} alt="" /></span>
          <div>
            <h2>{info[item]?.name ?? row?.name}<Warn code={item} /></h2>
            {row && (
              <div className="db-px">
                <b className="num">{won(row.price)}원</b>
                <span className={row.change > 0 ? "up" : row.change < 0 ? "down" : "muted"}>어제보다 {row.change > 0 ? "+" : ""}{won(row.change)}원 ({row.change_pct > 0 ? "+" : ""}{row.change_pct}%)</span>
              </div>
            )}
          </div>
          <div className="seg" role="group" aria-label="기간">
            {RANGES.map((r) => <button key={r.days} className={range === r.days ? "on" : ""} onClick={() => setRange(r.days)}>{r.label}</button>)}
          </div>
        </div>
        <Async state={hist} minHeight={280}>
          {() => <CandleChart points={candles} forecast={p?.forecast ?? []} height={280} />}
        </Async>
        {p && (
          <div className={`db-ai ${low ? "low" : ""}`}>
            <div><small>🤖 AI가 본 30일 뒤</small><b className={p.change_pct > 0 ? "up" : p.change_pct < 0 ? "down" : ""}>{won(p.predicted_price)}원</b><PctChange value={p.change_pct} className="small" /></div>
            {low && <span className="chip lowacc">❗ 예측 정확도 낮음 · 참고용</span>}
            <Link className="btn primary" to={`/ai?item=${item}`}>언제 팔지 보기</Link>
          </div>
        )}
      </section>
      <section className="card db-rank">
        <h3>실시간 품목 순위</h3>
        <div className="pills">
          {TABS.map((t) => <button key={t.key} className={`pill sm ${tab === t.key ? "on" : ""}`} onClick={() => setTab(t.key)}>{t.label}</button>)}
        </div>
        <ol className="db-list">
          {list.map((r, i) => (
            <Row key={r.item} n={i + 1} code={r.item} emoji={r.emoji} name={r.name} sub={isAi ? "AI 30일 뒤" : ""}
              price={isAi ? ai[r.item].predicted_price : r.price} pct={isAi ? ai[r.item].change_pct : r.change_pct}
              on={r.item === item} onClick={() => setPicked(r.item)} />
          ))}
        </ol>
      </section>
    </div>
  );
}

/** 아래 3칸: AI 상승 · AI 하락 · 내 관심 품목 (관심 품목이 없거나 로그인 전이면 많이 찾는 품목) */
export function BottomLists({ today, movers }) {
  const { user, updateProfile } = useAuth();
  const prices = Object.fromEntries((today?.items ?? []).map((p) => [p.item, p]));
  const ai = (movers ?? []).filter((m) => prices[m.item]);
  const ups = [...ai].sort((a, b) => b.change_pct - a.change_pct).slice(0, 5);
  const downs = [...ai].sort((a, b) => a.change_pct - b.change_pct).slice(0, 5);
  const favorites = user?.favorites ?? [];
  const mine = favorites.map((c) => prices[c]).filter(Boolean);
  const popular = (today?.items ?? []).slice(0, 5);
  const aiRows = (L) => L.map((m, i) => (
    <Row key={m.item} n={i + 1} code={m.item} emoji={prices[m.item].emoji} name={m.item_name} sub=""
      price={m.predicted_price} pct={m.change_pct} to={`/ai?item=${m.item}`} />
  ));
  const priceRows = (L, star) => L.map((p, i) => (
    <Row key={p.item} n={i + 1} code={p.item} emoji={p.emoji} name={p.name} sub="" price={p.price} pct={p.change_pct}
      to={`/market?item=${p.item}`} star={star} onStar={() => updateProfile({ favorites: [...favorites, p.item] })} />
  ));
  return (
    <div className="db-bottom">
      <section className="card"><h3>🤖 AI가 30일 뒤 오른다고 본 품목</h3><ol className="db-list">{aiRows(ups)}</ol></section>
      <section className="card"><h3>📉 AI가 30일 뒤 내린다고 본 품목</h3><ol className="db-list">{aiRows(downs)}</ol></section>
      {user && mine.length ? (
        <section className="card">
          <h3>⭐ 내 관심 품목 {mine.length > 5 && <Link className="link small" to="/mypage">전체 보기 →</Link>}</h3>
          <ol className="db-list">{priceRows(mine.slice(0, 5))}</ol>
        </section>
      ) : (
        <section className="card">
          <h3>🔥 많이 찾는 품목</h3>
          <ol className="db-list">{priceRows(popular, !!user)}</ol>
          {user ? (
            <div className="db-hint">☆를 눌러 관심 품목에 담아 보세요</div>
          ) : (
            <div className="db-hint">로그인하면 내 품목만 볼 수 있어요 <Link className="btn primary sm" to="/login">로그인</Link></div>
          )}
        </section>
      )}
    </div>
  );
}

// 홈 대시보드 (주식 앱처럼): 가격 예측·작물 추천 카드 → 지수 카드 8개 → 품목 차트 + 품목 순위 → AI 상승·하락·관심 품목
// 색: 오르면 빨강(.up), 내리면 파랑(.down). 가격 = 전국 도매시장 · 상 등급 · 원/kg
import { useState } from "react";
import { Link } from "react-router-dom";
import { getTopMovers, predict, recommendCrops } from "../api/ml";
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
function MiniForecast({ p, days = 30, height = 96, best }) {
  const w = 300;
  const hist = p.history.map((h) => h.price);
  const fc = p.forecast.slice(0, days);
  const all = [...hist, ...fc.flatMap((f) => [f.lower, f.upper]), best?.price ?? hist[0]];
  const lo = Math.min(...all), hi = Math.max(...all);
  const n = hist.length + fc.length - 1;
  const X = (i) => (i * w) / n;
  const Y = (v) => 6 + ((hi - v) / (hi - lo || 1)) * (height - 12);
  const k = hist.length - 1;
  const f = (sel) => fc.map((x, j) => `${X(k + j + 1)},${Y(sel(x))}`);
  // 가장 비싼 날이 그래프 기간(30일) 안이면 그 자리, 밖이면 오른쪽 끝에 점
  const bi = best ? fc.findIndex((x) => x.date === best.date) : -1;
  const bx = bi >= 0 ? X(k + bi + 1) : w - 4, by = best ? Y(Math.min(best.price, hi)) : 0;
  return (
    <svg className="mini-fc" viewBox={`0 0 ${w} ${height}`} preserveAspectRatio="none" role="img" aria-label="지난 가격과 AI 예측">
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
export function CoreFeatures({ items }) {
  // 3개월 뒤 가장 크게 오를 품목 (정확도가 낮거나 참고용인 품목은 빼고). 그래프·가장 비싼 날도 같은 3개월
  const movers90 = useAsync(() => getTopMovers({ horizon: 90, limit: 50 }));
  const pick = movers90.data?.filter((m) => !LOW_ACCURACY.has(m.item) && !m.reference).sort((a, b) => b.change_pct - a.change_pct)[0];
  const pred = useAsync(() => (pick ? predict({ item: pick.item, horizon: 90 }) : Promise.resolve(null)), [pick?.item]);
  const rec = useAsync(() => recommendCrops(formRequest(DEFAULT_FORM, todayIso())));
  const p = pred.data;
  const at = (d) => p && pctOf(p.forecast[d - 1].price, p.base_price);
  const best = p?.forecast.reduce((a, f) => (f.price > a.price ? f : a));
  const crops = (rec.data?.results ?? []).filter((r) => !r.demoted).slice(0, 3);
  const maxMargin = Math.max(...crops.map((c) => c.margin), 1);
  return (
    <section className="core-feat">
      <Link to={pick ? `/ai?item=${pick.item}` : "/ai"} className="cf ai">
        <div className="cf-main">
          <div className="cf-head"><span className="cf-tag">가격 예측</span></div>
          <h2>🤖 수확한 작물, <em>언제 팔까?</em></h2>
          {pick ? (
            <div className="cf-live">
              <span className="muted small">3개월 뒤 가장 크게 오를 품목</span>
              <b><ItemImage code={pick.item} emoji={items?.find((i) => i.code === pick.item)?.emoji} className="xs" /> {pick.item_name} {won(pick.predicted_price)}원 <PctChange value={pick.change_pct} /></b>
              <span className="muted small">지금 {p ? wonPerKg(p.base_price) : "…"}</span>
            </div>
          ) : <span className="muted small">예측 불러오는 중…</span>}
        </div>
        {p && (
          <div className="cf-side">
            <div className="mini-fc-wrap">
              <MiniForecast p={p} days={90} height={56} best={best} />
            </div>
            <div className="cf-best">
              <span className="ic" aria-hidden>💰</span>
              <div className="t"><small>가장 비싼 날</small><b>{shortDate(best.date)}</b></div>
              <div className="v"><b className="num">{won(best.price)}원</b><span className="up">▲ {pctOf(best.price, p.base_price).toFixed(1)}%</span></div>
            </div>
            <div className="cf-stats three">
              {[["1주 뒤", at(7)], ["1개월 뒤", at(30)], ["3개월 뒤", at(90)]].map(([t, v]) => (
                <div key={t}><small>{t}</small><PctChange value={v} /></div>
              ))}
            </div>
          </div>
        )}
        <span className="cf-go">가격 예측 보러 가기 →</span>
      </Link>
      <Link to="/recommend" className="cf rc">
        <div className="cf-head"><span className="cf-tag">작물 추천</span></div>
        <h2>🌱 내 땅에는 <em>무엇을 심을까?</em></h2>
        <ol className="cf-crops">
          {crops.length ? crops.map((c, i) => (
            <li key={`${c.crop}-${c.land_type}`} style={{ "--i": i }} title={`${shortDate(c.plant_date)} 시작 → ${shortDate(c.harvest_start)}~${shortDate(c.harvest_end)} 수확`}>
              <span className="n">{i + 1}</span>
              <span className="e">{c.emoji}</span>
              <span className="nm">{c.crop_name}</span>
              <span className="bar"><i style={{ width: `${(c.margin / maxMargin) * 100}%` }} /></span>
              <span className="v"><b>{won(Math.round(c.margin / 1e4))}만원</b></span>
            </li>
          )) : <li className="muted small">추천 불러오는 중…</li>}
        </ol>
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

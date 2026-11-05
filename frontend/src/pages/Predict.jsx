import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { getHorizons, getItems, getMarkets, predict } from "../api/ml";
import { Async, useAsync } from "../components/common";
import ForecastChart from "../components/ForecastChart";
import ItemImage from "../components/ItemImage";
import ItemPicker from "../components/ItemPicker";
import { ACCURACY, LOW_ACCURACY, bucketLabel, referenceOf } from "../mocks/accuracy";
import { LONG_RANGE_DAYS } from "../mocks/prediction";
import { addDays, daysBetween, md, shortDate, todayIso, won, wonPerKg } from "../utils/format";

const MAX_DAYS = 365;
const DEFAULT_MARKET = "110001"; // 서울가락

/** 오늘~고른 날짜 사이 가장 비싼 날·싼 날 (같은 값이면 가까운 날) */
function extremes(p) {
  let hi = null, lo = null;
  for (const f of p.forecast) {
    if (!hi || f.price > hi.price) hi = f;
    if (!lo || f.price < lo.price) lo = f;
  }
  const pct = (v) => Math.round(((v - p.base_price) / p.base_price) * 1000) / 10;
  return { hi: { ...hi, pct: pct(hi.price) }, lo: { ...lo, pct: pct(lo.price) } };
}
const sign = (v) => `${v > 0 ? "+" : ""}${v}%`;

/** 결과 맨 위: 고른 날 예상 가격(가장 크게) + 이 기간 최고·최저 가격 */
function PriceHero({ p, emoji, low }) {
  const { hi, lo } = extremes(p);
  const end = p.forecast.at(-1);
  const diff = p.predicted_price - p.base_price;
  const dir = p.change_pct > 0 ? "up" : p.change_pct < 0 ? "down" : "flat";
  return (
    <div className="ph">
      <div className={`ph-main ${dir}`}>
        <span className="ph-emo"><ItemImage code={p.item} emoji={emoji} alt="" /></span>
        <span className="ph-when">{shortDate(end.date)} · {p.horizon}일 후 · {p.market_name} 예상 경매 단가</span>
        <b className="ph-price num">{won(p.predicted_price)}<small>원/kg</small></b>
        <span className="ph-chg">
          <b className={dir}>{dir === "up" ? "▲" : dir === "down" ? "▼" : "–"} {Math.abs(p.change_pct).toFixed(1)}% ({diff > 0 ? "+" : ""}{won(diff)}원)</b>
          <span className="muted"> 오늘 {wonPerKg(p.base_price)}보다</span>
        </span>
        <span className="ph-range muted small">예상 범위 {won(end.lower)} ~ {won(end.upper)}원 · 오차 ±{Math.round(p.error_pct)}%{low ? " · ❗ 정확도 낮은 품목" : ""}</span>
      </div>
      <div className="ph-ext hi">
        <span>이 기간 최고 가격</span>
        <b className="num">{wonPerKg(hi.price)}</b>
        <em>{shortDate(hi.date)} · <i className="up">{sign(hi.pct)}</i></em>
      </div>
      <div className="ph-ext lo">
        <span>이 기간 최저 가격</span>
        <b className="num">{wonPerKg(lo.price)}</b>
        <em>{shortDate(lo.date)} · <i className="down">{sign(lo.pct)}</i></em>
      </div>
    </div>
  );
}

// 예측 기간(일) → 그 기간이 덮는 날 범위 (참고용 칸 칠하기)
const BUCKET_RANGE = { 7: [1, 10], 14: [11, 21], 30: [22, 60], 90: [61, 135], 180: [136, 180] };

/** 이 품목에서 "참고용"인 구간들 [{ x1, x2, label }] — 기준선보다 나쁜 기간 + 6개월보다 먼 날 */
function referenceZones(p) {
  const zones = [];
  (ACCURACY.items[p.item]?.reference_only ?? []).forEach((d) => {
    const [a, b] = BUCKET_RANGE[d];
    if (a > p.horizon) return;
    const last = zones.at(-1);
    if (last && last.b + 1 === a) last.b = Math.min(b, p.horizon);
    else zones.push({ a, b: Math.min(b, p.horizon), label: "참고용 · 기준선보다 나쁨" });
  });
  if (p.horizon > LONG_RANGE_DAYS) zones.push({ a: LONG_RANGE_DAYS + 1, b: p.horizon, label: "참고용 · 6개월 넘는 장기" });
  return zones.map((z) => ({ x1: addDays(p.base_date, z.a), x2: addDays(p.base_date, z.b), label: z.label }));
}

function Result({ p, emoji }) {
  const alert = p.alerts[0];
  const { hi, lo } = extremes(p);
  const long = p.horizon > LONG_RANGE_DAYS;
  const bad = (ACCURACY.items[p.item]?.reference_only ?? []).filter((d) => BUCKET_RANGE[d][0] <= p.horizon);
  const ref = p.reference ?? referenceOf(p.item, p.horizon);
  const low = LOW_ACCURACY.has(p.item);
  return (
    <section className="card">
      <PriceHero p={p} emoji={emoji} low={low} />
      <div className="chips">
        <span className="chip">
          🛡️ 신뢰도 지수 <b>{p.confidence}</b>/100
          <span className="meter"><i style={{ width: `${p.confidence}%` }} /></span>
        </span>
        <span className="chip">📏 예측 오차 <b>±{Math.round(p.error_pct)}%</b></span>
        {low && <span className="chip lowacc">❗ 예측 정확도 낮음</span>}
        {ref && <span className="chip ref">🔖 참고용</span>}
        {alert && <span className="chip warn">⚠️ 이상기후 경보 구간 {md(alert.start)} ~ {md(alert.end)}</span>}
      </div>
      {low && (
        <div className="low-acc">
          <span className="ip-warn big">!</span>
          <div>
            <b>{p.item_name}은(는) 예측 정확도가 낮은 품목이에요</b>
            <p>[경고 문구는 추후 추가될 내용입니다] 이 품목은 가격 변동이 커서 모델 검증 오차가 큰 편이에요 (1개월 뒤 ±{Math.round(ACCURACY.items[p.item]?.wape["30"] ?? 0)}%). 예측값은 방향만 참고해 주세요.</p>
          </div>
        </div>
      )}
      <div className={low ? "chart-low" : undefined}>
        {low && <span className="chart-low-tag">⚠ 예측 정확도 낮음 · 참고만 하세요 (문구 추후 추가)</span>}
        <ForecastChart p={p} height={270}
          marks={[{ date: hi.date, price: hi.price, label: "최고", color: "#d92d20" }, { date: lo.date, price: lo.price, label: "최저", color: "#1d63c9" }]}
          zones={referenceZones(p)} />
      </div>
      {bad.length > 0 && (
        <p className="ai-long">🔖 <b>{p.item_name} {bad.map(bucketLabel).join("·")} 예측은 참고용이에요.</b> 모델 검증에서 이 품목·기간은 "오늘 가격이 그대로 간다"고 본 기준선보다 오차가 컸어요.</p>
      )}
      {long && (
        <p className="ai-long">ℹ️ <b>6개월이 넘는 장기 예측은 참고용이에요.</b> 검증하지 않은 기간이라 범위(띠)를 더 넓게 보여 줘요.</p>
      )}
      <details className="more-info">
        <summary>예측 오차·신뢰도는 어떻게 계산하나요?</summary>
        오차 범위(띠)·신뢰도 = 모델 검증 오차(WAPE, 2025-07~) · {p.item_name} 1주 ±{Math.round(ACCURACY.items[p.item]?.wape["7"] ?? 0)}% · 1개월 ±{Math.round(ACCURACY.items[p.item]?.wape["30"] ?? 0)}% · 6개월 ±{Math.round(ACCURACY.items[p.item]?.wape["180"] ?? ACCURACY.average_wape["180"])}% · 신뢰도 = 100 − 오차 · 날씨·기후 변수와 과거 시세를 함께 학습한 모델
      </details>
      {alert ? (
        <div className="banner" style={{ marginTop: 14 }}>
          ⚠️
          <div className="small">
            <b>예측이 깨지는 구간 분석</b>
            <div>
              {md(alert.start)}~{md(alert.end)} {alert.reason}. 과거 유사 이상기후 구간에서 모델 평균 오차(MAPE)가{" "}
              {alert.mape_normal}% → {alert.mape_anomaly}%로 커졌습니다. 이 구간의 예측값은 참고용으로만 활용하세요.
            </div>
          </div>
        </div>
      ) : null}
      <p className="muted small" style={{ margin: "10px 0 0" }}>{p.market_name} 경매 단가(원/kg) · 기준일 {shortDate(p.base_date)} · 모델 {p.model_version}</p>
    </section>
  );
}

export default function Predict() {
  const [params, setParams] = useSearchParams();
  const options = useAsync(async () => {
    const [items, horizons, markets] = await Promise.all([getItems(), getHorizons(), getMarkets()]);
    return { items, horizons, markets };
  });
  const opts = options.data;
  const item = params.get("item") || opts?.items[0]?.code;
  const market = params.get("market") || DEFAULT_MARKET;
  const today = todayIso();
  // 고를 수 있는 날짜: 내일 ~ 오늘 + 365일. 빠른 선택 버튼은 GET /horizons
  const [target, setTarget] = useState(() => {
    const d = params.get("date");
    return d && daysBetween(today, d) >= 1 && daysBetween(today, d) <= MAX_DAYS ? d : addDays(today, 30);
  });
  const horizon = daysBetween(today, target);
  const go = (next) => setParams({ item, market, date: target, ...next }, { replace: true });

  const pickDate = (d) => {
    if (!d) return;
    const next = addDays(today, Math.min(Math.max(daysBetween(today, d), 1), MAX_DAYS));
    setTarget(next);
    go({ date: next });
  };

  const ready = opts && item && horizon >= 1;
  const result = useAsync(() => (ready ? predict({ item, horizon, market }) : Promise.resolve(null)), [ready, item, horizon, market]);
  const bySido = (o) => o.markets.reduce((g, m) => ((g[m.sido] = g[m.sido] ?? []).push(m), g), {});

  return (
    <div className="page">
      <div className="page-head">
        <h1>AI 가격 예측</h1>
        <p>도매시장별 예상 경매 단가 · 1kg 기준 · 최대 1년 뒤까지</p>
      </div>
      <Async state={options}>
        {(o) => (
          <div className="predict-layout stack">
            <section className="card pred-bar">
              <div className="field">
                <label htmlFor="item">품목</label>
                <ItemPicker items={o.items} value={item} onChange={(c) => go({ item: c })} warn={LOW_ACCURACY} />
              </div>
              <div className="field">
                <label htmlFor="market">도매시장</label>
                <select id="market" className="input" value={market} onChange={(e) => go({ market: e.target.value })}>
                  {Object.entries(bySido(o)).map(([sido, ms]) => (
                    <optgroup key={sido} label={sido}>{ms.map((m) => <option key={m.code} value={m.code}>{m.name}</option>)}</optgroup>
                  ))}
                </select>
              </div>
              <div className="field">
                <label htmlFor="target">예측 날짜</label>
                <input id="target" type="date" className="input" value={target} min={addDays(today, 1)} max={addDays(today, MAX_DAYS)} onChange={(e) => pickDate(e.target.value)} />
                <div className="pills">
                  {o.horizons.map((h) => (
                    <button key={h.days} className={`pill sm ${horizon === h.days ? "on" : ""}`} onClick={() => pickDate(addDays(today, h.days))}>
                      {h.label} 후
                    </button>
                  ))}
                </div>
              </div>
            </section>
            <Async state={result} minHeight={420}>
              {(p) => <Result p={p} emoji={o.items.find((i) => i.code === p.item)?.emoji} />}
            </Async>
          </div>
        )}
      </Async>
    </div>
  );
}

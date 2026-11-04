import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { getHorizons, getItems, getMarkets, predict } from "../api/ml";
import { Async, PctChange, useAsync } from "../components/common";
import ForecastChart from "../components/ForecastChart";
import ItemImage from "../components/ItemImage";
import ItemPicker from "../components/ItemPicker";
import { LONG_RANGE_DAYS } from "../mocks/prediction";
import { addDays, daysBetween, md, shortDate, todayIso, wonPerKg } from "../utils/format";

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

function ExtremeCards({ p }) {
  const { hi, lo } = extremes(p);
  return (
    <div className="ai-ext">
      <div className="hi">
        <span>이 기간 중 가장 비싸게 팔 수 있는 날</span>
        <b>{shortDate(hi.date)}</b>
        <em>{wonPerKg(hi.price)} <i className="up">({sign(hi.pct)})</i></em>
      </div>
      <div className="lo">
        <span>이 기간 중 가장 싼 날</span>
        <b>{shortDate(lo.date)}</b>
        <em>{wonPerKg(lo.price)} <i className="down">({sign(lo.pct)})</i></em>
      </div>
    </div>
  );
}

function Result({ p, horizonLabel }) {
  const alert = p.alerts[0];
  const { hi, lo } = extremes(p);
  const long = p.horizon > LONG_RANGE_DAYS;
  return (
    <section className="card">
      <div className="chips">
        <span className="chip">
          🛡️ 신뢰도 지수 <b>{p.confidence}</b>/100
          <span className="meter"><i style={{ width: `${p.confidence}%` }} /></span>
        </span>
        {alert && <span className="chip warn">⚠️ 이상기후 경보 구간 {md(alert.start)} ~ {md(alert.end)}</span>}
      </div>
      <ExtremeCards p={p} />
      <ForecastChart p={p} height={340}
        marks={[{ date: hi.date, price: hi.price, label: "최고", color: "#d92d20" }, { date: lo.date, price: lo.price, label: "최저", color: "#1d63c9" }]}
        longFrom={long ? addDays(p.base_date, LONG_RANGE_DAYS) : null} />
      {long && (
        <p className="ai-long">ℹ️ <b>장기 예측은 참고용이에요.</b> {LONG_RANGE_DAYS}일(3개월)이 넘는 구간은 오차가 커서 범위(띠)를 넓게 보여 줘요. 날짜가 가까워지면 다시 확인해 주세요.</p>
      )}
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
      ) : (
        <p className="muted small" style={{ marginTop: 10 }}>{horizonLabel}까지 이상기후 경보 구간이 없습니다.</p>
      )}
      <p className="muted small" style={{ margin: "10px 0 0" }}>{p.market_name} 도매시장 기준 · 모델 버전 {p.model_version} · 기준일 {shortDate(p.base_date)}</p>
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
  const horizonLabel = `${shortDate(target)} (${horizon}일 후)`;
  const bySido = (o) => o.markets.reduce((g, m) => ((g[m.sido] = g[m.sido] ?? []).push(m), g), {});

  return (
    <div className="page">
      <div className="page-head">
        <h1>AI 가격 예측</h1>
        <p>과거 기상(기온·강수·일조) + 기후 변수 + 시세를 결합한 예측 모델 · 도매시장별 · 가격은 1kg 기준 · 최대 1년</p>
      </div>
      <Async state={options}>
        {(o) => (
          <div className="predict-layout">
            <section className="card" style={{ display: "grid", gap: 18 }}>
              <div className="field">
                <label htmlFor="item">품목</label>
                <ItemPicker items={o.items} value={item} onChange={(c) => go({ item: c })} />
              </div>
              <div className="field">
                <label htmlFor="market">도매시장</label>
                <select id="market" className="input" value={market} onChange={(e) => go({ market: e.target.value })}>
                  {Object.entries(bySido(o)).map(([sido, ms]) => (
                    <optgroup key={sido} label={sido}>{ms.map((m) => <option key={m.code} value={m.code}>{m.name}</option>)}</optgroup>
                  ))}
                </select>
                <span className="hint">공영 도매시장 {o.markets.length}곳 중 팔 곳을 골라요</span>
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
                <span className="hint">내일부터 1년 뒤({shortDate(addDays(today, MAX_DAYS))})까지 고를 수 있어요</span>
              </div>
              {result.data && (
                <div className="summary-box">
                  <span className="summary-img"><ItemImage code={result.data.item} emoji={o.items.find((i) => i.code === result.data.item)?.emoji} alt="" /></span>
                  <div className="muted small">{shortDate(result.data.forecast.at(-1).date)} ({horizon}일 후)<br />{result.data.market_name} 예상 도매가</div>
                  <div className="price num">{wonPerKg(result.data.predicted_price)}</div>
                  <PctChange value={result.data.change_pct} className="small" />
                  <span className="muted small"> vs 오늘 {wonPerKg(result.data.base_price)}</span>
                </div>
              )}
            </section>
            <Async state={result} minHeight={420}>
              {(p) => <Result p={p} horizonLabel={horizonLabel} />}
            </Async>
          </div>
        )}
      </Async>
    </div>
  );
}

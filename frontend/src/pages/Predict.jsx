import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { getHorizons, getItems, getRegions, predict } from "../api/ml";
import { Async, PctChange, useAsync } from "../components/common";
import ForecastChart from "../components/ForecastChart";
import { md, shortDate, wonPerKg } from "../utils/format";

function Result({ p, horizonLabel }) {
  const alert = p.alerts[0];
  return (
    <section className="card">
      <div className="chips">
        <span className="chip">
          🛡️ 신뢰도 지수 <b>{p.confidence}</b>/100
          <span className="meter"><i style={{ width: `${p.confidence}%` }} /></span>
        </span>
        {alert && <span className="chip warn">⚠️ 이상기후 경보 구간 {md(alert.start)} ~ {md(alert.end)}</span>}
      </div>
      <ForecastChart p={p} height={340} />
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
        <p className="muted small" style={{ marginTop: 10 }}>{horizonLabel} 예측 구간에 이상기후 경보가 없습니다.</p>
      )}
      <p className="muted small" style={{ margin: "10px 0 0" }}>모델 버전 {p.model_version} · 기준일 {shortDate(p.base_date)}</p>
    </section>
  );
}

export default function Predict() {
  const [params, setParams] = useSearchParams();
  const options = useAsync(async () => {
    const [items, horizons, regions] = await Promise.all([getItems(), getHorizons(), getRegions()]);
    return { items, horizons, regions };
  });
  const opts = options.data;
  const item = params.get("item") || opts?.items[0]?.code;
  const [horizon, setHorizon] = useState(null);
  const [region, setRegion] = useState(null);

  useEffect(() => {
    if (!opts) return;
    setHorizon((h) => h ?? opts.horizons[0]?.days);
    setRegion((r) => r ?? opts.regions[0]?.code);
  }, [opts]);

  const ready = opts && item && horizon && region;
  const result = useAsync(() => (ready ? predict({ item, horizon, region }) : Promise.resolve(null)), [ready, item, horizon, region]);
  const horizonLabel = opts?.horizons.find((h) => h.days === horizon)?.label ?? "";

  return (
    <div className="page">
      <div className="page-head">
        <h1>AI 가격 예측</h1>
        <p>과거 기상(기온·강수·일조) + 기후 변수 + 시세를 결합한 예측 모델 · 가격은 1kg 기준</p>
      </div>
      <Async state={options}>
        {(o) => (
          <div className="predict-layout">
            <section className="card" style={{ display: "grid", gap: 18 }}>
              <div className="field">
                <label htmlFor="item">품종</label>
                <select id="item" className="input" value={item} onChange={(e) => setParams({ item: e.target.value })}>
                  {o.items.map((i) => (
                    <option key={i.code} value={i.code}>{i.emoji} {i.name}</option>
                  ))}
                </select>
              </div>
              {/* 지역이 1개(전국)뿐이면 선택 박스를 숨긴다 — 지역별 예측을 켜면 자동으로 나타남 */}
              {o.regions.length > 1 && (
                <div className="field">
                  <label htmlFor="region">지역</label>
                  <select id="region" className="input" value={region ?? ""} onChange={(e) => setRegion(e.target.value)}>
                    {o.regions.map((r) => <option key={r.code} value={r.code}>{r.name}</option>)}
                  </select>
                </div>
              )}
              <div className="field">
                <label>예측 시점</label>
                <div className="pills">
                  {o.horizons.map((h) => (
                    <button key={h.days} className={`pill ${horizon === h.days ? "on" : ""}`} onClick={() => setHorizon(h.days)}>
                      {h.label}
                    </button>
                  ))}
                </div>
              </div>
              {result.data && (
                <div className="summary-box">
                  <div className="muted small">{horizonLabel} 후 예상 도매가</div>
                  <div className="price num">{wonPerKg(result.data.predicted_price)}</div>
                  <PctChange value={result.data.change_pct} className="small" />
                  <span className="muted small"> vs 오늘 {wonPerKg(result.data.base_price)}</span>
                </div>
              )}
              {o.regions.length === 1 && <p className="muted small" style={{ margin: 0 }}>현재 {o.regions[0].name} 기준 예측만 제공합니다.</p>}
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

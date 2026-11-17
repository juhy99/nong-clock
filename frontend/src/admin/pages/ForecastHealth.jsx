import { useState } from "react";
import { getForecastHealth, getForecastVsActual } from "../../api/adminOps";
import { Async, SectionHead, useAsync } from "../../components/common";
import { itemOf, varietyOf } from "../../mocks/items50";
import { md, won } from "../../utils/format";

/**
 * 예측 점검 (11-17): 예측 표를 통째로 훑어 이상한 곳만 보여 줌 (Spring /api/admin/ops/forecast-health · forecast-vs-actual)
 * - 건강 검진: 가장 최근 기준일 표. 하루 사이 크게 바뀌는 곳 · 지금 가격과 크게 다른 품목 · 거래가 오래된 품목 · 앞 판과 달라진 정도
 * - 예측과 실제: 지난 예측의 목표일이 지나면 그날 실제 경매 단가와 견줌 (품목 전체 · 전국)
 * 모델은 바꾸지 않음 — 보기만 하는 화면
 */
const FLAG = { stale: ["거래 오래됨", "amber"], far: ["지금 값과 크게 다름", "red"], no_30: ["30일 안 예측 없음", "blue"] };
const vName = (item, vid) => (vid === "ALL" ? "전체" : varietyOf(item, vid)?.label ?? vid);
/** 품목 이름은 사용자 사이트와 같은 이름으로 (DB 이름은 "브로코리(녹색꽃양배추)" · "메론" 처럼 원자료 표기) */
const iName = (r) => itemOf(r.item_code)?.name ?? r.item_name;
const pct = (v) => `${v > 0 ? "+" : ""}${v}%`;

function Health() {
  const state = useAsync(getForecastHealth);
  const [all, setAll] = useState(false);
  const [q, setQ] = useState("");
  return (
    <Async state={state}>
      {(d) => {
        if (!d.bases.length) return <div className="card state">예측 표(price_forecast_daily)가 아직 없어요. 데이터 수집 → 예측 갱신을 먼저 돌려 주세요.</div>;
        const b = d.bases[0];
        const flagged = d.items.filter((r) => r.flags.some((f) => f !== "no_30"));
        const none = d.items.filter((r) => r.flags.includes("no_30"));
        const shown = all ? d.items : d.items.filter((r) => r.flags.length);
        const steps = d.steps.filter((r) => !q.trim() || `${iName(r)}${vName(r.item_code, r.variety_id)}`.includes(q.trim()));
        return (
          <>
            <div className="stat-row">
              <div className="stat"><div className="muted small">예측 기준일</div><div className="v num">{md(b.base_date)}</div><div className="muted small">{md(b.first_date)} ~ {b.last_date}</div></div>
              <div className="stat"><div className="muted small">품목 · 품종</div><div className="v num">{won(b.series)}</div><div className="muted small">{won(b.rows)}줄</div></div>
              <div className={`stat ${d.steps_total ? "stat-amber" : ""}`}><div className="muted small">하루 {Math.round((d.step_ratio - 1) * 100)}% 넘게 바뀌는 곳</div><div className="v num">{won(d.steps_total)}</div><div className="muted small">산지 · 작형이 바뀌는 날</div></div>
              <div className={`stat ${flagged.length ? "stat-amber" : ""}`}><div className="muted small">살펴볼 품목</div><div className="v num">{flagged.length}</div><div className="muted small">30일 안 예측 없음 {none.length}</div></div>
              <div className="stat"><div className="muted small">참고값 · 폭락 보정</div><div className="v num">{won(b.off_rows)} · {won(b.crash_rows)}</div><div className="muted small">줄</div></div>
            </div>

            <section className="card">
              <SectionHead title="품목 점검" desc={`품목 전체 · 전국 기준. 거래 오래됨 = 마지막 거래가 기준일보다 ${d.stale_days}일 넘게 앞인데 예측이 있음 · 크게 다름 = 30일 안 예측이 지금 값의 ${d.far_ratio}배를 넘거나 1/${d.far_ratio} 밑`}
                right={<label className="small"><input type="checkbox" checked={all} onChange={(e) => setAll(e.target.checked)} /> 50품목 모두 보기</label>} />
              <p className="muted small" style={{ marginTop: 0 }}>사용자 화면은 지난 3년 그 달 거래량이 1년의 1% 밑인 달을 숨겨요. 여기는 숨기기 전 표 그대로예요.</p>
              {shown.length === 0 ? <div className="state">살펴볼 품목이 없어요 ✅</div> : (
                <div className="table-wrap"><table className="table">
                  <thead><tr><th>품목</th><th>마지막 거래</th><th className="num">지금 값 (7일 평균)</th><th className="num">30일 안 최저 ~ 최고</th><th className="num">예측 날 수</th><th>표시</th></tr></thead>
                  <tbody>
                    {shown.map((r) => (
                      <tr key={r.item_code}>
                        <td><b>{iName(r)}</b> <span className="muted small">품종 {r.varieties}</span></td>
                        <td className="small num">{r.last_trade ?? "-"}</td>
                        <td className="num">{r.base_price == null ? "-" : `${won(r.base_price)}원`}</td>
                        <td className="num small">{r.max_30 == null ? "-" : `${won(r.min_30)} ~ ${won(r.max_30)}원${r.base_price ? ` (×${(r.min_30 / r.base_price).toFixed(2)} ~ ×${(r.max_30 / r.base_price).toFixed(2)})` : ""}`}</td>
                        <td className="num small">{r.days_30} / {won(r.days_all)}</td>
                        <td>{r.flags.length ? r.flags.map((f) => <span key={f} className={`badge ${FLAG[f][1]}`} style={{ marginRight: 4 }}>{FLAG[f][0]}</span>) : <span className="muted small">정상</span>}</td>
                      </tr>
                    ))}
                  </tbody>
                </table></div>
              )}
            </section>

            <section className="card">
              <SectionHead title={`하루 사이 크게 바뀌는 곳 ${won(d.steps_total)}곳`} desc="붙은 거래일끼리 견줌 · 변화가 큰 순 150곳. 사용자 예측 화면에는 🔀 안내가 붙어요 (품목 안 산지 · 작형이 바뀌는 날)"
                right={<input className="input" style={{ maxWidth: 180 }} placeholder="품목 · 품종 찾기" value={q} onChange={(e) => setQ(e.target.value)} />} />
              <div className="table-wrap" style={{ maxHeight: 420, overflowY: "auto" }}><table className="table">
                <thead><tr><th>품목</th><th>품종</th><th>날짜</th><th className="num">앞날 → 그날</th><th className="num">변화</th><th>규칙</th></tr></thead>
                <tbody>
                  {steps.map((r) => (
                    <tr key={`${r.item_code}${r.variety_id}${r.target_date}`}>
                      <td><b>{iName(r)}</b></td>
                      <td className="small">{vName(r.item_code, r.variety_id)}</td>
                      <td className="small num">{md(r.prev_date)} → {md(r.target_date)}</td>
                      <td className="num small">{won(r.prev_price)} → {won(r.price)}원</td>
                      <td className="num"><b className={r.change_pct > 0 ? "up" : "down"}>{pct(r.change_pct)}</b></td>
                      <td className="small muted">{r.model}</td>
                    </tr>
                  ))}
                </tbody>
              </table></div>
            </section>

            {d.diff && (
              <section className="card">
                <SectionHead title={`앞 판(${md(d.prev_base)})과 달라진 정도`} desc="같은 목표일끼리 견줌 · 품목 전체. 새 자료가 들어와 예측이 얼마나 움직였는지 — 갑자기 크게 달라진 품목은 입력 자료를 확인" />
                <div className="table-wrap"><table className="table">
                  <thead><tr><th>품목</th><th className="num">겹치는 날</th><th className="num">평균 변화</th><th className="num">가장 큰 변화</th></tr></thead>
                  <tbody>
                    {d.diff.slice(0, 12).map((r) => (
                      <tr key={r.item_code}><td><b>{iName(r)}</b></td><td className="num small">{r.days}</td><td className="num">{r.mean_change_pct}%</td><td className="num">{r.max_change_pct}%</td></tr>
                    ))}
                  </tbody>
                </table></div>
                <p className="muted small">기준일 기록: {d.bases.map((x) => `${md(x.base_date)} (${won(x.rows)}줄)`).join(" · ")}</p>
              </section>
            )}
          </>
        );
      }}
    </Async>
  );
}

function VsActual() {
  const state = useAsync(getForecastVsActual);
  return (
    <Async state={state}>
      {(d) => {
        if (d.error || !d.total?.n) return <div className="card state">{d.error ?? "아직 견줄 날이 없어요. 예측을 만든 뒤 그 목표일의 실제 시세가 들어오면 여기에 쌓여요."}</div>;
        const t = d.total;
        return (
          <>
            <div className="stat-row">
              <div className="stat"><div className="muted small">견준 예측</div><div className="v num">{won(t.n)}건</div><div className="muted small">{md(t.first_date)} ~ {md(t.last_date)} · 기준일 {t.bases}개</div></div>
              <div className="stat"><div className="muted small">실제와 평균 차이</div><div className="v num">{t.error_pct}%</div><div className="muted small">정확도 {(100 - t.error_pct).toFixed(1)}%</div></div>
              <div className="stat"><div className="muted small">치우침</div><div className="v num">{pct(t.bias_pct)}</div><div className="muted small">{t.bias_pct > 0 ? "예측이 실제보다 높은 편" : "예측이 실제보다 낮은 편"}</div></div>
            </div>
            <div className="banner info small"><span>ℹ️</span><div>품목 전체 예측과 그날 전국 경매 단가(금액 ÷ 물량)를 견줘요 (참고값으로 표시된 예측은 뺌). 모델 성능 화면의 시험 점수(2025~, 단위별)와 재는 방법이 달라 숫자가 같지 않아요 — 여기는 <b>서비스에 실제로 나간 예측</b>이 맞았는지 보는 곳이에요. 견준 날이 적을 때는 참고만 하세요.</div></div>
            <div className="two-col">
              <section className="card">
                <SectionHead title="거리별" desc="목표일 − 기준일 (달력 일)" />
                <table className="table"><thead><tr><th>거리</th><th className="num">건</th><th className="num">평균 차이</th><th className="num">치우침</th></tr></thead>
                  <tbody>{d.by_distance.map((r) => <tr key={r.distance}><td>{r.distance}</td><td className="num small">{won(r.n)}</td><td className="num">{r.error_pct}%</td><td className="num">{pct(r.bias_pct)}</td></tr>)}</tbody></table>
              </section>
              <section className="card">
                <SectionHead title="기준일별" desc="그날 만든 예측이 얼마나 맞았나" />
                <table className="table"><thead><tr><th>기준일</th><th className="num">건</th><th className="num">평균 차이</th><th className="num">치우침</th></tr></thead>
                  <tbody>{d.by_base.map((r) => <tr key={r.base_date}><td className="num">{r.base_date}</td><td className="num small">{won(r.n)}</td><td className="num">{r.error_pct}%</td><td className="num">{pct(r.bias_pct)}</td></tr>)}</tbody></table>
              </section>
            </div>
            <section className="card">
              <SectionHead title="품목별" desc="차이가 큰 순" />
              <div className="table-wrap" style={{ maxHeight: 420, overflowY: "auto" }}><table className="table">
                <thead><tr><th>품목</th><th className="num">건</th><th className="num">평균 차이</th><th className="num">치우침</th></tr></thead>
                <tbody>{d.by_item.map((r) => <tr key={r.item_code}><td><b>{iName(r)}</b></td><td className="num small">{r.n}</td><td className="num">{r.error_pct}%</td><td className="num">{pct(r.bias_pct)}</td></tr>)}</tbody>
              </table></div>
            </section>
            <section className="card">
              <SectionHead title="가장 최근에 견준 예측" desc={d.recent.length ? `기준일 ${d.recent[0].base_date} 예측 · 차이가 큰 순` : ""} />
              <div className="table-wrap" style={{ maxHeight: 420, overflowY: "auto" }}><table className="table">
                <thead><tr><th>목표일</th><th>품목</th><th className="num">예측</th><th className="num">실제</th><th className="num">차이</th><th className="num">거래량</th></tr></thead>
                <tbody>{d.recent.map((r) => (
                  <tr key={`${r.item_code}${r.target_date}`}><td className="num small">{md(r.target_date)}</td><td><b>{iName(r)}</b></td><td className="num">{won(r.predicted)}원</td><td className="num">{won(r.actual)}원</td>
                    <td className="num"><b className={r.diff_pct > 0 ? "up" : "down"}>{pct(r.diff_pct)}</b></td><td className="num small">{won(r.volume_t)}톤</td></tr>
                ))}</tbody>
              </table></div>
            </section>
          </>
        );
      }}
    </Async>
  );
}

export default function ForecastHealth() {
  const [tab, setTab] = useState("health");
  return (
    <>
      <h1>예측 점검</h1>
      <div className="tabs" style={{ marginBottom: 16 }}>
        <button className={tab === "health" ? "on" : ""} onClick={() => setTab("health")}>🩺 건강 검진</button>
        <button className={tab === "vs" ? "on" : ""} onClick={() => setTab("vs")}>🎯 예측과 실제</button>
      </div>
      {tab === "health" ? <Health /> : <VsActual />}
    </>
  );
}

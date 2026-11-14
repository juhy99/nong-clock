import { useMemo, useState } from "react";
import { getModelPerformance } from "../../api/admin";
import { Async, SectionHead, useAsync } from "../../components/common";

// 모델 성능: 화면 가격 예측에 쓰는 최종 모델(팀원 76판 · 11-13 확정)의 시험 정확도 (shared/final_model_accuracy.json)
// 정확도 = 100 − 단위마다 평균 |예측÷실제 − 1|(%) 의 단위 중앙값 — 높을수록 좋음. 비교 기준 = "작년 같은 시기 가격"
const tone = (v) => (v == null ? "" : v >= 85 ? "#1f9d55" : v >= 75 ? "#7a9a1f" : v >= 65 ? "#e0a100" : "#d93025");
const f1 = (v) => (v == null ? "-" : v.toFixed(1));

const CARDS = [
  { key: "H1-5", src: "day_total", label: "1~5거래일 뒤", sub: (t) => `u7d만 ${f1(t.u7d)} · 원인 모델만 ${f1(t.cause)}` },
  { key: "H6-14", src: "day_total", label: "6~14거래일 뒤", sub: (t) => `u7d만 ${f1(t.u7d)} · 원인 모델만 ${f1(t.cause)}` },
  { key: "h1-3", src: "month_total", label: "1~3달 뒤 (달 평균)", sub: (t) => `원인 모델만 ${f1(t.cause)}` },
  { key: "h4-6", src: "month_total", label: "4~6달 뒤 (달 평균)", sub: (t) => `원인 모델만 ${f1(t.cause)}` },
  { key: "h7-12", src: "month_total", label: "7~12달 뒤 (달 평균)", sub: (t) => `원인 모델만 ${f1(t.cause)}` },
];
const COLS = [
  { key: "d1", label: "1~5일" }, { key: "d2", label: "6~14일" },
  { key: "m1", label: "1~3달" }, { key: "m2", label: "4~6달" }, { key: "m3", label: "7~12달" },
];

function Kpi({ c, t }) {
  const gap = t.final_same_rows - t.last_year;
  return (
    <div className="stat">
      <div className="muted small">{c.label}</div>
      <div className="v" style={{ color: tone(t.final) }}>{f1(t.final)}%</div>
      <div className="muted small">작년 같은 시기 {f1(t.last_year)}% ({gap >= 0 ? "+" : ""}{gap.toFixed(1)}%p)</div>
      <div className="muted small">{c.sub(t)} · {t.units}단위</div>
    </div>
  );
}

function ByDistance({ title, rows, unit, cols }) {
  return (
    <div className="table-wrap" style={{ marginBottom: 16 }}>
      <table className="table mp-table">
        <thead>
          <tr><th>{title}</th>{rows.map((r) => <th key={r.h} className="r">{r.h}{unit}</th>)}</tr>
        </thead>
        <tbody>
          {cols.map(([k, name]) => (
            <tr key={k}>
              <td className={k === "final" ? "" : "muted small"}>{name}</td>
              {rows.map((r) => <td key={r.h} className="r num">{k === "final" ? <b style={{ color: tone(r[k]) }}>{f1(r[k])}</b> : f1(r[k])}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function ModelPerformance() {
  const [q, setQ] = useState("");
  const [item, setItem] = useState("전체");
  const [sortBy, setSortBy] = useState("d1");
  const [onlyWorse, setOnlyWorse] = useState(false);
  const state = useAsync(getModelPerformance);

  return (
    <section className="card">
      <Async state={state}>
        {(perf) => <Body perf={perf} {...{ q, setQ, item, setItem, sortBy, setSortBy, onlyWorse, setOnlyWorse }} />}
      </Async>
    </section>
  );
}

function Body({ perf, q, setQ, item, setItem, sortBy, setSortBy, onlyWorse, setOnlyWorse }) {
  const items = useMemo(() => ["전체", ...[...new Set(perf.units.map((u) => u.item))].sort((a, b) => a.localeCompare(b, "ko"))], [perf]);
  const word = q.trim();
  const worse = (u) => COLS.some(({ key }) => u[key] && u[key][1] != null && u[key][0] < u[key][1]);
  const rows = perf.units
    .filter((u) => item === "전체" || u.item === item)
    .filter((u) => !word || u.unit.includes(word))
    .filter((u) => !onlyWorse || worse(u))
    .sort((a, b) => (b[sortBy]?.[0] ?? -1) - (a[sortBy]?.[0] ?? -1));
  const tm = perf.teammate;

  return (
    <>
      <SectionHead
        title="모델 성능 모니터링"
        desc={`${perf.model_version} · 시험 기간 ${perf.period.check} (달 예측 ${perf.period.month_check}) · 정확도(%) — 높을수록 좋음`}
      />
      <ul className="muted small" style={{ margin: "0 0 14px", paddingLeft: 18, lineHeight: 1.7 }}>
        <li>{perf.rule.day}</li>
        <li>{perf.rule.month}</li>
        <li>{perf.rule.far} — 시험 줄이 없어 점수 없음</li>
      </ul>
      <div className="stat-row" style={{ marginBottom: 16 }}>
        {CARDS.map((c) => <Kpi key={c.key} c={c} t={perf[c.src][c.key]} />)}
      </div>

      <ByDistance title="거래일 뒤" unit="" rows={perf.day} cols={[["final", "최종"], ["u7d", "u7d만"], ["cause", "원인 모델만"], ["last_year", "작년 같은 주"]]} />
      <ByDistance title="달 뒤" unit="달" rows={perf.month} cols={[["final", "최종 (v4)"], ["cause", "원인 모델만"], ["last_year", "작년 같은 달"]]} />

      <h3 style={{ margin: "20px 0 8px" }}>예측 단위별 ({perf.units.length}단위)</h3>
      <div className="mp-ctrl">
        <select className="input" style={{ maxWidth: 160 }} value={item} onChange={(e) => setItem(e.target.value)} aria-label="품목 고르기">
          {items.map((i) => <option key={i} value={i}>{i}</option>)}
        </select>
        <label className="small"><input type="checkbox" checked={onlyWorse} onChange={(e) => setOnlyWorse(e.target.checked)} /> 작년 같은 시기보다 낮은 칸이 있는 단위만</label>
        <input className="input" style={{ maxWidth: 200 }} placeholder="단위 검색" value={q} onChange={(e) => setQ(e.target.value)} aria-label="단위 검색" />
      </div>
      <div className="table-wrap">
        <table className="table mp-table">
          <thead>
            <tr>
              <th>예측 단위</th>
              {COLS.map((c) => (
                <th key={c.key} className="r">
                  <button className="link small" onClick={() => setSortBy(c.key)} title="정확도 높은 순으로 정렬">{c.label}{sortBy === c.key ? " ▼" : ""}</button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((u) => (
              <tr key={u.unit}>
                <td>{u.unit}</td>
                {COLS.map(({ key }) => {
                  const v = u[key];
                  if (!v) return <td key={key} className="r num">-</td>;
                  const bad = v[1] != null && v[0] < v[1];
                  return (
                    <td key={key} className="r num" title={`최종 ${v[0]}% · 작년 같은 시기 ${v[1] ?? "-"}%`}>
                      <b style={{ color: tone(v[0]) }}>{f1(v[0])}</b>
                      {bad && <em className="mp-ref">작년보다 낮음</em>}
                      <small className="muted">작년 {f1(v[1])}</small>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h3 style={{ margin: "20px 0 8px" }}>팀원 시험 성적 (76판, 팀원 자료 그대로)</h3>
      <div className="table-wrap">
        <table className="table mp-table">
          <thead><tr><th>달 예측 구간</th><th className="r">단위</th><th className="r">v4</th><th className="r">작년 그대로</th></tr></thead>
          <tbody>
            {tm.monthly.map((r) => (
              <tr key={r.구간}><td>{r.구간}</td><td className="r num">{r.단위}</td><td className="r num"><b>{f1(r.우리)}</b></td><td className="r num">{f1(r.작년그대로)}</td></tr>
            ))}
            <tr><td>일 예측 u7d (1~14거래일)</td><td className="r num">{tm.daily_h1.단위수}</td><td className="r num"><b>{f1(tm.daily_h1.새기준)}</b></td><td className="r num">{f1(tm.daily_h1.작년같은주)}</td></tr>
            {tm.weekly.map((r) => (
              <tr key={r.H}><td>주 예측 u7d {r.H}주 뒤</td><td className="r num">{r.단위수}</td><td className="r num"><b>{f1(r.새기준)}</b></td><td className="r num">{f1(r.작년같은주)}</td></tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="muted small" style={{ marginTop: 12, lineHeight: 1.7 }}>
        {perf.metric} · 섞는 비율은 {perf.period.pick} 줄로만 골랐고, 위 점수는 그 뒤 기간(고를 때 안 쓴 줄)이에요 ·
        작년 같은 시기 = 목표일 364일 전 앞뒤 3일(일) / 작년 같은 달(달) 가격, 그 값이 있는 줄만으로 비교 (괄호 안 %p) ·
        일 점수는 매주 토요일 기준으로 낸 예측 줄 · 팀원 표는 팀원 정답·줄 기준이라 위 점수와 조금 달라요 ·
        예측 대상일이 지나면 서비스 운영 중 "예측 vs 실제" 비교가 추가될 예정이에요.
      </p>
    </>
  );
}

import { useState } from "react";
import { getModelPerformance } from "../../api/admin";
import { getItems } from "../../api/ml";
import { Async, SectionHead, useAsync } from "../../components/common";

// 모델 성능: 107품목 가격 예측 모델(최종 앙상블)의 검증 기간 오차 (shared/model_accuracy.json)
// 오차 = WAPE(%) — 낮을수록 좋음. 기준선 = "오늘 가격이 그대로 간다"
const GROUPS = ["전체", "연중", "제철", "비수기뚜렷", "계절편차", "수입위주", "참고용"];
const tone = (v) => (v == null ? "" : v <= 15 ? "#1f9d55" : v <= 25 ? "#7a9a1f" : v <= 35 ? "#e0a100" : "#d93025");

function Kpi({ perf, h }) {
  const s = perf.summary[`${h.label}|day`];
  const m = perf.summary[`${h.label}|mon`];
  return (
    <div className="stat">
      <div className="muted small">{h.label} 뒤 · 품목 평균 오차</div>
      <div className="v" style={{ color: tone(s.fin) }}>{s.fin.toFixed(1)}%</div>
      <div className="muted small">기준선 {s.base.toFixed(1)}% · 공통 모델 {s.com.toFixed(1)}%{s.ly != null ? ` · 작년 같은 시기 ${s.ly.toFixed(1)}%` : ""}</div>
      <div className="muted small">기준선보다 나은 품목 {s.better}/{s.n}{m ? ` · 달 평균 정답 ${m.fin.toFixed(1)}%` : ""}</div>
    </div>
  );
}

export default function ModelPerformance() {
  const [q, setQ] = useState("");
  const [group, setGroup] = useState("전체");
  const [sortBy, setSortBy] = useState("7");
  const state = useAsync(async () => {
    const [perf, items] = await Promise.all([getModelPerformance(), getItems()]);
    return { perf, items: Object.fromEntries(items.map((i) => [i.code, i])) };
  });

  return (
    <section className="card">
      <Async state={state}>
        {({ perf, items }) => {
          const word = q.trim();
          const rows = Object.entries(perf.items)
            .map(([code, r]) => ({ code, ...r, info: items[code] }))
            .filter((r) => (group === "전체" ? true : group === "참고용" ? r.reference_only.length > 0 : group === "수입위주" ? r.import_heavy : r.season === group))
            .filter((r) => !word || (r.info?.name ?? r.model_name).includes(word))
            .sort((a, b) => (a.wape[sortBy] ?? 999) - (b.wape[sortBy] ?? 999));
          return (
            <>
              <SectionHead
                title="모델 성능 모니터링"
                desc={`${perf.model_version} · 검증 기간 ${perf.period.hold} · 품목별 예측 오차 WAPE(%) — 낮을수록 좋음 · 정답 = 공영도매시장 경매 단가(원/kg)`}
              />
              <div className="stat-row" style={{ marginBottom: 16 }}>
                {perf.horizons.map((h) => <Kpi key={h.days} perf={perf} h={h} />)}
              </div>
              <div className="mp-ctrl">
                <div className="pills">
                  {GROUPS.map((g) => <button key={g} className={`pill sm ${group === g ? "on" : ""}`} onClick={() => setGroup(g)}>{g}</button>)}
                </div>
                <input className="input" style={{ maxWidth: 200 }} placeholder="품목 검색" value={q} onChange={(e) => setQ(e.target.value)} aria-label="품목 검색" />
              </div>
              <div className="table-wrap">
                <table className="table mp-table">
                  <thead>
                    <tr>
                      <th>품목</th><th>시즌 유형</th>
                      {perf.horizons.map((h) => (
                        <th key={h.days} className="r">
                          <button className="link small" onClick={() => setSortBy(String(h.days))} title="오차 낮은 순으로 정렬">{h.label}{sortBy === String(h.days) ? " ▲" : ""}</button>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r) => (
                      <tr key={r.code}>
                        <td>{r.info?.emoji} {r.info?.name ?? r.model_name} <small className="muted">{r.info?.code4}</small></td>
                        <td className="muted small">{r.season}{r.import_heavy ? " · 수입위주" : ""}</td>
                        {perf.horizons.map((h) => {
                          const v = r.wape[h.days], base = r.baseline[h.days], ref = r.reference_only.includes(h.days);
                          return (
                            <td key={h.days} className="r num" title={v == null ? "" : `최종 ${v}% · 기준선 ${base}% · 공통 ${r.common[h.days]}%${r.last_year[h.days] != null ? ` · 작년 ${r.last_year[h.days]}%` : ""}`}>
                              {v == null ? "-" : (
                                <>
                                  <b style={{ color: tone(v) }}>{v.toFixed(1)}</b>
                                  {ref && <em className="mp-ref">참고용</em>}
                                  <small className="muted">기준 {base.toFixed(1)}</small>
                                </>
                              )}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="muted small" style={{ marginTop: 12, lineHeight: 1.7 }}>
                {rows.length}개 품목 · 칸 = 최종 앙상블 오차(%), 아래 작은 숫자 = 기준선(오늘 가격 그대로) 오차 · 3·6개월은 "그날 가격" 정답 기준(달 평균 정답은 위 카드) ·
                <b> 참고용</b> = 최종이 기준선보다 0.1%p 넘게 나쁜 품목·기간 (양배추 1·3·6개월, 당근 3·6개월, 무 1개월, 석류 6개월) — 예측 화면에도 "참고용"으로 표시해요 ·
                6개월보다 먼 예측(최대 1년)은 검증하지 않아 화면에서 6개월 오차보다 넓게 잡고 참고용으로 표시해요 ·
                예측 대상일이 지나면 서비스 운영 중 "예측 vs 실제" 비교가 추가될 예정이에요.
              </p>
            </>
          );
        }}
      </Async>
    </section>
  );
}

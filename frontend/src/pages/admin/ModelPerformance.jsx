import { getModelPerformance } from "../../api/admin";
import { getHorizons, getItems } from "../../api/ml";
import { Async, SectionHead, useAsync } from "../../components/common";

const color = (v, target) => (v >= target ? "#1f9d55" : v >= target - 15 ? "#e0a100" : "#d93025");

export default function ModelPerformance() {
  const state = useAsync(async () => {
    const [perf, items, horizons] = await Promise.all([getModelPerformance(), getItems(), getHorizons()]);
    return { perf, items: Object.fromEntries(items.map((i) => [i.code, i])), horizons };
  });
  return (
    <section className="card">
      <Async state={state}>
        {({ perf, items, horizons }) => {
          const avg = (d) => perf.rows.reduce((s, r) => s + (r.accuracy[d] ?? 0), 0) / perf.rows.length;
          const passed = (d) => perf.rows.filter((r) => r.accuracy[d] >= perf.target).length;
          return (
            <>
              <SectionHead title="모델 성능 모니터링" desc={`${perf.model_version} · 품목·기간별 과거 적중률(%) · 목표 ${perf.target}%`} />
              <div className="stat-row" style={{ marginBottom: 16 }}>
                {horizons.map((h) => (
                  <div className="stat" key={h.days}>
                    <div className="muted small">{h.label} 평균 적중률</div>
                    <div className="v" style={{ color: color(avg(h.days), perf.target) }}>{avg(h.days).toFixed(1)}%</div>
                    <div className="muted small">목표 달성 {passed(h.days)}/{perf.rows.length} 품목</div>
                  </div>
                ))}
              </div>
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr><th>품목</th>{horizons.map((h) => <th key={h.days}>{h.label}</th>)}</tr>
                  </thead>
                  <tbody>
                    {perf.rows.map((r) => (
                      <tr key={r.item}>
                        <td>{items[r.item]?.emoji} {items[r.item]?.name ?? r.item}</td>
                        {horizons.map((h) => {
                          const v = r.accuracy[h.days];
                          return (
                            <td key={h.days}>
                              {v == null ? "-" : (
                                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                                  <div className="bar" style={{ flex: 1 }}><i style={{ width: `${v}%`, background: color(v, perf.target) }} /></div>
                                  <span className="num small" style={{ width: 40 }}>{v.toFixed(1)}</span>
                                </div>
                              )}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="muted small" style={{ marginTop: 12 }}>
                예측 대상일이 지나면 "예측 vs 실제" 비교가 추가될 예정입니다. (현재 값은 팀원 v1 결과 파일 기준)
              </p>
            </>
          );
        }}
      </Async>
    </section>
  );
}

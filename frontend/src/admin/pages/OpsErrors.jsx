import { getOpsErrors } from "../../api/adminOps";
import { Async, SectionHead, useAsync } from "../../components/common";

/**
 * 오류 기록 (11-17): 회원 · 게시판 · 시세 서버(Spring)가 내보낸 문제 응답 (Spring /api/admin/ops/errors)
 * 서버 오류(5xx) · 요청 수 제한(429) · 로그인 실패. 최근 300건 + 48시간 시간대별 횟수, 서버를 다시 켜면 비워짐
 */
const KIND = { server: ["서버 오류", "red"], limit: ["요청 제한", "amber"], login: ["로그인 실패", "blue"] };

export default function OpsErrors() {
  const state = useAsync(getOpsErrors);
  return (
    <>
      <h1>오류 기록</h1>
      <Async state={state}>
        {(d) => {
          const max = Math.max(1, ...d.hours.map((h) => h.server + h.limit + h.login));
          return (
            <>
              <div className="stat-row">
                <div className={`stat ${d.total.server ? "stat-amber" : ""}`}><div className="muted small">서버 오류 (5xx)</div><div className="v num">{d.total.server}</div><div className="muted small">사용자가 겪은 버그 — 0이어야 정상</div></div>
                <div className="stat"><div className="muted small">요청 제한 (429)</div><div className="v num">{d.total.limit}</div><div className="muted small">너무 빠른 요청을 막은 횟수</div></div>
                <div className={`stat ${d.total.login >= 20 ? "stat-amber" : ""}`}><div className="muted small">로그인 실패</div><div className="v num">{d.total.login}</div><div className="muted small">한 곳에서 몰리면 비밀번호 대입 시도</div></div>
              </div>
              <div className="banner info small"><span>ℹ️</span><div>최근 {d.since_hours}시간 · 최근 {d.max_events}건만 서버 메모리에 남겨요 (서버를 다시 켜면 비워짐). 요청 본문 · 이메일 · 비밀번호는 남기지 않고 IP 끝자리는 가려요. nginx 가 앞에서 막은 요청과 AI 예측 서버(ml-api) 오류는 여기 없어요.</div></div>
              <section className="card">
                <SectionHead title="시간대별" desc="문제가 있었던 시간만" right={<button className="btn sm" onClick={state.reload}>새로 고침</button>} />
                {d.hours.length === 0 ? <div className="state">기록된 문제가 없어요 ✅</div> : (
                  <div style={{ display: "grid", gap: 6 }}>
                    {d.hours.map((h) => (
                      <div key={h.hour} style={{ display: "grid", gridTemplateColumns: "120px 1fr 150px", gap: 10, alignItems: "center" }}>
                        <span className="small num">{h.hour.slice(5).replace("T", " ")}시</span>
                        <span style={{ display: "flex", height: 14, background: "var(--soft)", borderRadius: 4, overflow: "hidden" }}>
                          <i style={{ width: `${(h.server / max) * 100}%`, background: "#d9534f" }} /><i style={{ width: `${(h.limit / max) * 100}%`, background: "#e0a100" }} /><i style={{ width: `${(h.login / max) * 100}%`, background: "#4a7fd4" }} />
                        </span>
                        <span className="small muted num">오류 {h.server} · 제한 {h.limit} · 로그인 {h.login}</span>
                      </div>
                    ))}
                  </div>
                )}
              </section>
              <section className="card">
                <SectionHead title={`최근 기록 ${d.events.length}건`} desc="새 것부터" />
                {d.events.length === 0 ? <div className="state">기록이 없어요</div> : (
                  <div className="table-wrap" style={{ maxHeight: 520, overflowY: "auto" }}><table className="table">
                    <thead><tr><th>시각</th><th>종류</th><th>요청</th><th>IP</th><th>오류 종류</th></tr></thead>
                    <tbody>{d.events.map((e, i) => (
                      <tr key={i}><td className="small num">{e.at.slice(5).replace("T", " ")}</td><td><span className={`badge ${KIND[e.kind][1]}`}>{KIND[e.kind][0]} {e.status}</span></td>
                        <td className="small"><code>{e.method} {e.path}</code></td><td className="small num">{e.ip}</td><td className="small muted">{e.note}</td></tr>
                    ))}</tbody>
                  </table></div>
                )}
              </section>
            </>
          );
        }}
      </Async>
    </>
  );
}

import { getSystemStatus } from "../../api/admin";
import { ML_API_BASE } from "../../api/client";
import { Async, SectionHead, useAsync } from "../../components/common";

export default function SystemStatus() {
  const state = useAsync(getSystemStatus);
  return (
    <section className="card">
      <SectionHead
        title="서버·API 상태"
        desc={`ML API 는 실제로 확인합니다 (${ML_API_BASE}/health). 나머지는 개발 전입니다.`}
        right={<button className="btn sm" onClick={state.reload} disabled={state.loading}>{state.loading ? "확인 중…" : "다시 확인"}</button>}
      />
      <Async state={state}>
        {(rows) => (
          <table className="table">
            <thead>
              <tr><th>서비스</th><th>상태</th><th className="r">응답 속도</th><th>상세</th></tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.name}>
                  <td><b>{r.name}</b></td>
                  <td>
                    <span className={`dot ${r.ok ? "ok" : r.pending ? "wait" : "bad"}`} />{" "}
                    {r.ok ? "정상" : r.pending ? "준비 중" : "응답 없음"}
                  </td>
                  <td className="r num">{r.ms != null ? `${r.ms}ms` : "-"}</td>
                  <td className="muted small">{r.detail}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Async>
    </section>
  );
}

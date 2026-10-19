import { getCollectionStatus } from "../../api/admin";
import { Async, SectionHead, useAsync } from "../../components/common";
import { dateTime, won } from "../../utils/format";

const BADGE = { 정상: "green", 테스트: "amber", 미연결: "", 실패: "red" };

export default function DataStatus() {
  const state = useAsync(getCollectionStatus);
  return (
    <section className="card">
      <SectionHead title="데이터 수집 현황" desc="수집 스크립트별 마지막 실행 시각과 보유 데이터 범위" />
      <Async state={state}>
        {(rows) => (
          <>
            <div className="stat-row" style={{ marginBottom: 16 }}>
              <div className="stat"><div className="muted small">수집 원천</div><div className="v">{rows.length}개</div></div>
              <div className="stat"><div className="muted small">정상</div><div className="v">{rows.filter((r) => r.status === "정상").length}개</div></div>
              <div className="stat"><div className="muted small">미연결·테스트</div><div className="v">{rows.filter((r) => r.status !== "정상").length}개</div></div>
            </div>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr><th>데이터</th><th>주기</th><th>마지막 실행</th><th>보유 범위</th><th className="r">행 수</th><th>상태</th><th>비고</th></tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.source}>
                      <td><b>{r.source}</b></td>
                      <td className="small">{r.schedule}</td>
                      <td className="small num">{r.last_run ? dateTime(r.last_run) : "-"}</td>
                      <td className="small">{r.latest_data}</td>
                      <td className="r num">{won(r.rows)}</td>
                      <td><span className={`badge ${BADGE[r.status]}`}>{r.status}</span></td>
                      <td className="muted small">{r.note}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Async>
    </section>
  );
}

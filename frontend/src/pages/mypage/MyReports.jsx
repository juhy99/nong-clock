import { Link } from "react-router-dom";
import { getMyReports } from "../../api/report";
import { useAuth } from "../../components/AuthContext";
import { Async, SectionHead, useAsync } from "../../components/common";
import { dateTime } from "../../utils/format";

const STATUS_BADGE = { 접수: "red", 검토중: "amber", 처리완료: "green", 반려: "" };

export default function MyReports() {
  const { user } = useAuth();
  const state = useAsync(() => getMyReports(user.id), [user.id]);
  return (
    <section className="card">
      <SectionHead title="신고 내역" desc="경매 상세 화면의 '🚨 신고' 버튼으로 접수한 신고와 처리 결과" />
      <Async state={state} empty="접수한 신고가 없습니다">
        {(rows) => (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr><th>접수</th><th>유형</th><th>대상</th><th>상태</th><th>처리 결과</th></tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id}>
                    <td className="small num">{dateTime(r.created_at)}</td>
                    <td className="small">{r.type}</td>
                    <td className="small">
                      {r.auction_id ? <Link className="link small" to={`/auctions/${r.auction_id}`}>{r.target}</Link> : r.target}
                    </td>
                    <td><span className={`badge ${STATUS_BADGE[r.status]}`}>{r.status}</span></td>
                    <td className="small">{r.status === "처리완료" || r.status === "반려" ? r.memo || "-" : <span className="muted">처리 중</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Async>
    </section>
  );
}

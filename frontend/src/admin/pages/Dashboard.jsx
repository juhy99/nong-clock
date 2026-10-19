import { Link } from "react-router-dom";
import { getAllAuctions, getReports, getUsers } from "../../api/admin";
import { getAllPosts } from "../../api/board";
import { Async, SectionHead, useAsync } from "../../components/common";
import { dateTime } from "../../utils/format";
import SystemStatus from "./SystemStatus";

/** 관리자 첫 화면: 처리할 일 + 서버 상태 */
export default function Dashboard() {
  const state = useAsync(async () => {
    const [reports, auctions, users, posts] = await Promise.all([getReports(), getAllAuctions(), getUsers(), getAllPosts()]);
    const today = new Date().toDateString();
    const live = auctions.filter((a) => a.status === "진행중" && new Date(a.ends_at) > new Date());
    return {
      openReports: reports.filter((r) => r.status === "접수" || r.status === "검토중"),
      tiles: [
        ["처리 대기 신고", reports.filter((r) => r.status === "접수" || r.status === "검토중").length, "/reports", "red"],
        ["승인 대기 경매", auctions.filter((a) => a.status === "승인대기").length, "/auctions", "amber"],
        ["진행 중 경매", live.length, "/auctions"],
        ["오늘 올라온 글", posts.filter((p) => new Date(p.created_at).toDateString() === today).length, "/board"],
        ["숨김 처리된 글", posts.filter((p) => p.hidden).length, "/board"],
        ["활동 회원", users.filter((u) => u.status === "정상").length, "/members"],
      ],
    };
  });

  return (
    <>
      <h1>대시보드</h1>
      <Async state={state}>
        {(d) => (
          <>
            <div className="stat-row">
              {d.tiles.map(([label, v, to, tone]) => (
                <Link key={label} to={to} className={`stat ${tone && v > 0 ? `stat-${tone}` : ""}`}>
                  <div className="muted small">{label}</div>
                  <div className="v num">{v}</div>
                </Link>
              ))}
            </div>
            <section className="card">
              <SectionHead title="처리할 신고" right={<Link className="link" to="/reports">전체 보기 →</Link>} />
              {d.openReports.length === 0 ? (
                <p className="muted" style={{ margin: 0 }}>처리할 신고가 없습니다 🎉</p>
              ) : (
                <table className="table">
                  <tbody>
                    {d.openReports.slice(0, 5).map((r) => (
                      <tr key={r.id}>
                        <td><span className="badge">{r.type}</span></td>
                        <td>{r.target}</td>
                        <td className="small muted num">{dateTime(r.created_at)}</td>
                        <td className="small">{r.status}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </section>
          </>
        )}
      </Async>
      <SystemStatus />
    </>
  );
}

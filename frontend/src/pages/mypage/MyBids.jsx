import { Link } from "react-router-dom";
import { displayStatus, getMyBids } from "../../api/auction";
import { useAuth } from "../../components/AuthContext";
import { Async, SectionHead, useAsync } from "../../components/common";
import { won } from "../../utils/format";

export default function MyBids() {
  const { user } = useAuth();
  const bids = useAsync(() => getMyBids(user.id), [user.id]);
  return (
    <section className="card">
      <SectionHead title="입찰 참여" desc="참여한 경매와 현재 최고가" />
      <Async state={bids} empty="아직 입찰한 경매가 없습니다">
        {(rows) => (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr><th>상품</th><th className="r">내 최고 입찰</th><th className="r">현재 최고가</th><th>상태</th></tr>
              </thead>
              <tbody>
                {rows.map((r) => {
                  const st = displayStatus(r);
                  return (
                    <tr key={r.id}>
                      <td><Link to={`/auctions/${r.id}`} className="link">{r.emoji} {r.title}</Link></td>
                      <td className="r num">{won(r.my_bid)}원</td>
                      <td className="r num">{won(r.current_bid)}원</td>
                      <td>
                        {st === "진행중" ? (
                          r.leading ? <span className="badge green">최고가</span> : <span className="badge red">상회 입찰됨</span>
                        ) : st === "낙찰" ? (
                          r.leading ? <span className="badge blue">낙찰</span> : <span className="badge">패찰</span>
                        ) : (
                          <span className="badge">{st}</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Async>
    </section>
  );
}

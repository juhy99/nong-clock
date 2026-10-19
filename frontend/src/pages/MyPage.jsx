import { Link } from "react-router-dom";
import { getMyBids } from "../api/auction";
import { USER_TYPE_LABEL, useAuth } from "../components/AuthContext";
import { Async, SectionHead, useAsync } from "../components/common";
import { won } from "../utils/format";

export default function MyPage() {
  const { user } = useAuth();
  const bids = useAsync(() => getMyBids(user.id), [user.id]);
  return (
    <div className="page">
      <div className="page-head">
        <h1>마이페이지</h1>
      </div>
      <div className="split">
        <section className="card">
          <SectionHead title="내 입찰 현황" desc="참여한 경매와 현재 최고가" />
          <Async state={bids} empty="아직 입찰한 경매가 없습니다">
            {(rows) => (
              <table className="table">
                <thead>
                  <tr><th>상품</th><th className="r">내 최고 입찰</th><th className="r">현재 최고가</th><th>상태</th></tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.id}>
                      <td><Link to={`/auctions/${r.id}`} className="link">{r.title}</Link></td>
                      <td className="r num">{won(r.my_bid)}원</td>
                      <td className="r num">{won(r.current_bid)}원</td>
                      <td>{r.leading ? <span className="badge green">최고가</span> : <span className="badge red">상회 입찰됨</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Async>
        </section>
        <section className="card">
          <SectionHead title="내 정보" />
          <dl className="kv">
            <dt>이름</dt><dd>{user.name}</dd>
            <dt>이메일</dt><dd>{user.email}</dd>
            <dt>회원 유형</dt><dd>{USER_TYPE_LABEL[user.type]}</dd>
            <dt>연락처</dt><dd>{user.phone}</dd>
            <dt>지역</dt><dd>{user.region}</dd>
            {user.farm_name && (<><dt>농장명</dt><dd>{user.farm_name}</dd></>)}
            <dt>가입일</dt><dd>{user.joined}</dd>
          </dl>
        </section>
      </div>
    </div>
  );
}

import { Fragment, useState } from "react";
import { Link } from "react-router-dom";
import { getAllAuctions, getUsers, setAuctionStatus, setUserStatus } from "../../api/admin";
import { USER_TYPE_LABEL, useAuth } from "../../components/AuthContext";
import { Async, SectionHead, useAsync } from "../../components/common";
import { dateTime, won } from "../../utils/format";
import BidCancelPanel from "./BidCancelPanel";

const AUCTION_BADGE = { 진행중: "green", 승인대기: "amber", 중단: "red", 취소: "" };
const USER_BADGE = { 정상: "green", 정지: "red", 탈퇴: "" };

export default function Members() {
  const { user: me } = useAuth();
  const users = useAsync(getUsers);
  const auctions = useAsync(getAllAuctions);
  const [q, setQ] = useState("");
  const [bidsOpen, setBidsOpen] = useState(null);

  return (
    <>
      <section className="card">
        <SectionHead
          title="회원 관리"
          desc="이용 정지된 회원은 로그인할 수 없습니다"
          right={<input className="input" style={{ maxWidth: 200 }} placeholder="이름·이메일 검색" value={q} onChange={(e) => setQ(e.target.value)} />}
        />
        <Async state={users}>
          {(rows) => (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr><th>이름</th><th>이메일</th><th>유형</th><th>지역</th><th>가입일</th><th>상태</th><th /></tr>
                </thead>
                <tbody>
                  {rows.filter((u) => `${u.name}${u.email}`.includes(q.trim())).map((u) => (
                    <tr key={u.id}>
                      <td><b>{u.name}</b>{u.farm_name && <div className="muted small">{u.farm_name}</div>}</td>
                      <td className="small">{u.email}</td>
                      <td className="small">{USER_TYPE_LABEL[u.type]}</td>
                      <td className="small">{u.region}</td>
                      <td className="small num">{u.joined}</td>
                      <td><span className={`badge ${USER_BADGE[u.status] ?? ""}`}>{u.status}</span></td>
                      <td className="r">
                        {u.id !== me.id && u.status !== "탈퇴" && (
                          <button className="btn sm" onClick={async () => { await setUserStatus(u.id, u.status === "정상" ? "정지" : "정상"); users.reload(); }}>
                            {u.status === "정상" ? "이용 정지" : "정지 해제"}
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Async>
      </section>
      <section className="card">
        <SectionHead title="경매 관리" desc="새 경매는 승인 후 노출됩니다 · 문제 상품은 중단, 비정상 입찰은 '입찰 관리'에서 취소할 수 있습니다" />
        <Async state={auctions}>
          {(rows) => (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr><th>#</th><th>상품</th><th>판매자</th><th className="r">현재가</th><th>마감</th><th>상태</th><th /></tr>
                </thead>
                <tbody>
                  {rows.map((a) => (
                    <Fragment key={a.id}>
                      <tr>
                        <td className="muted">{a.id}</td>
                        <td><Link className="link" to={`/auctions/${a.id}`}>{a.emoji} {a.title}</Link></td>
                        <td className="small">{a.seller}</td>
                        <td className="r num">{won(a.current_bid)}원</td>
                        <td className="small num">{dateTime(a.ends_at)}</td>
                        <td><span className={`badge ${AUCTION_BADGE[a.status] ?? ""}`}>{a.status}</span></td>
                        <td className="r" style={{ whiteSpace: "nowrap" }}>
                          {a.status === "승인대기" && <button className="btn sm primary" onClick={async () => { await setAuctionStatus(a.id, "진행중"); auctions.reload(); }}>승인</button>}{" "}
                          {a.status === "진행중" && <button className="btn sm danger" onClick={async () => { if (confirm("이 경매를 중단할까요?")) { await setAuctionStatus(a.id, "중단"); auctions.reload(); } }}>중단</button>}
                          {a.status === "중단" && <button className="btn sm" onClick={async () => { await setAuctionStatus(a.id, "진행중"); auctions.reload(); }}>재개</button>}{" "}
                          {a.bid_count > 0 && <button className="btn sm" onClick={() => setBidsOpen(bidsOpen === a.id ? null : a.id)}>{bidsOpen === a.id ? "닫기" : "입찰 관리"}</button>}
                        </td>
                      </tr>
                      {bidsOpen === a.id && (
                        <tr>
                          <td colSpan={7} style={{ background: "#fafaf7" }}>
                            <BidCancelPanel auctionId={a.id} onDone={auctions.reload} />
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Async>
      </section>
    </>
  );
}

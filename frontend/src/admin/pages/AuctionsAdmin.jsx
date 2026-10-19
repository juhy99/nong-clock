import { Fragment, useState } from "react";
import { getAllAuctions, setAuctionStatus } from "../../api/admin";
import { Async, SectionHead, useAsync } from "../../components/common";
import { dateTime, won } from "../../utils/format";
import { SITE_URL } from "../siteUrl";
import BidCancelPanel from "./BidCancelPanel";

const AUCTION_BADGE = { 진행중: "green", 승인대기: "amber", 중단: "red", 취소: "" };

export default function AuctionsAdmin() {
  const auctions = useAsync(getAllAuctions);
  const [bidsOpen, setBidsOpen] = useState(null);

  return (
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
                      <td><a className="link" href={`${SITE_URL}/auctions/${a.id}`} target="_blank" rel="noreferrer">{a.emoji} {a.title} ↗</a></td>
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
  );
}

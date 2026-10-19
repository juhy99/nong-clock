import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getAuctions } from "../api/auction";
import { Async, useAsync } from "../components/common";
import Photo from "../components/Photo";
import { remain, won } from "../utils/format";

/** 1초마다 남은 시간 갱신 */
export function useNow(intervalMs = 1000) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(t);
  }, [intervalMs]);
  return now;
}

export function AuctionCard({ a }) {
  const now = useNow();
  return (
    <Link to={`/auctions/${a.id}`} className="auction-card">
      <div className="auction-thumb">{a.images?.length ? <Photo src={a.images[0]} alt={a.title} /> : a.emoji}</div>
      <div className="auction-body">
        <span className="title">{a.title}</span>
        <span className="muted small">{a.bid_count ? "현재 최고가" : "시작가"}</span>
        <b style={{ fontSize: 19 }} className="num">{won(a.current_bid)}원</b>
        <div className="auction-meta">
          <span className="timer">⏱ {remain(new Date(a.ends_at) - now)}</span>
          <span>🔨 {a.bid_count}건</span>
        </div>
      </div>
    </Link>
  );
}

const SORTS = [
  ["popular", "입찰 많은 순"],
  ["ending", "마감 임박 순"],
  ["price", "가격 높은 순"],
];

export default function Auctions() {
  const [sort, setSort] = useState("popular");
  const state = useAsync(() => getAuctions({ sort }), [sort]);
  return (
    <div className="page">
      <div className="page-head">
        <h1>경매 마켓</h1>
        <p>산지 농가가 직접 올린 상품에 입찰하세요. 최소 입찰 단위는 1,000원입니다.</p>
      </div>
      <div className="pills">
        {SORTS.map(([k, label]) => (
          <button key={k} className={`pill ${sort === k ? "on" : ""}`} onClick={() => setSort(k)}>
            {label}
          </button>
        ))}
      </div>
      <Async state={state} empty="진행 중인 경매가 없습니다">
        {(rows) => (
          <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(230px, 1fr))" }}>
            {rows.map((a) => <AuctionCard key={a.id} a={a} />)}
          </div>
        )}
      </Async>
    </div>
  );
}

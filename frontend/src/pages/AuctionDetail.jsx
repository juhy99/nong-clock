import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { MIN_INCREMENT, getAuction, placeBid } from "../api/auction";
import { useAuth } from "../components/AuthContext";
import { Async, useAsync } from "../components/common";
import { dateTime, remain, won } from "../utils/format";
import { useNow } from "./Auctions";

export default function AuctionDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const state = useAsync(() => getAuction(id), [id]);
  const now = useNow();
  const [amount, setAmount] = useState("");
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);

  async function submit(e, a) {
    e.preventDefault();
    setBusy(true);
    setMsg(null);
    try {
      await placeBid(a.id, user, Number(amount));
      setMsg({ ok: true, text: `${won(Number(amount))}원으로 입찰했습니다.` });
      setAmount("");
      state.reload();
    } catch (err) {
      setMsg({ ok: false, text: err.message });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page">
      <Link to="/auctions" className="link">← 경매 목록</Link>
      <Async state={state}>
        {(a) => {
          const left = new Date(a.ends_at) - now;
          const live = a.status === "진행중" && left > 0;
          const min = a.bid_count === 0 ? a.start_price : a.current_bid + MIN_INCREMENT;
          return (
            <div className="two-col">
              <div className="detail-thumb">{a.emoji}</div>
              <div className="card" style={{ display: "grid", gap: 16, alignContent: "start" }}>
                <div>
                  <span className={`badge ${live ? "green" : "amber"}`}>{live ? "진행중" : a.status === "진행중" ? "마감" : a.status}</span>
                  <h1 style={{ marginTop: 8 }}>{a.title}</h1>
                </div>
                <div>
                  <div className="muted small">{a.bid_count ? "현재 최고가" : "시작가"}</div>
                  <div style={{ fontSize: 32, fontWeight: 800 }} className="num">{won(a.current_bid)}원</div>
                  <div className="timer">⏱ 남은 시간 {remain(left)}</div>
                </div>
                <dl className="kv">
                  <dt>산지</dt><dd>{a.origin}</dd>
                  <dt>총 중량</dt><dd>{a.weight_kg}kg <span className="muted">(1kg당 {won(a.current_bid / a.weight_kg)}원)</span></dd>
                  <dt>시작가</dt><dd>{won(a.start_price)}원</dd>
                  <dt>입찰 수</dt><dd>{a.bid_count}건</dd>
                  <dt>판매자</dt><dd>{a.seller}</dd>
                </dl>
                <p className="muted" style={{ margin: 0 }}>{a.description}</p>
                {live && (
                  <form onSubmit={(e) => submit(e, a)} style={{ display: "grid", gap: 8 }}>
                    <label className="small"><b>입찰가</b> <span className="muted">(최소 {won(min)}원, {won(MIN_INCREMENT)}원 단위)</span></label>
                    <div style={{ display: "flex", gap: 8 }}>
                      <input className="input" type="number" step={MIN_INCREMENT} min={min} placeholder={String(min)} value={amount} onChange={(e) => setAmount(e.target.value)} required />
                      <button className="btn primary" disabled={busy || !user}>입찰하기</button>
                    </div>
                    {!user && <span className="hint">입찰하려면 <Link to={`/login?next=/auctions/${a.id}`} className="link">로그인</Link>이 필요합니다.</span>}
                    {msg && <span className={`hint ${msg.ok ? "ok" : "error"}`}>{msg.text}</span>}
                  </form>
                )}
                <div>
                  <h3 style={{ marginBottom: 6 }}>입찰 기록</h3>
                  {a.bids.length === 0 ? (
                    <p className="muted small">아직 입찰이 없습니다.</p>
                  ) : (
                    <table className="table">
                      <tbody>
                        {[...a.bids].reverse().map((b, i) => (
                          <tr key={i}>
                            <td>{b.user === user?.id ? <b>나</b> : b.user.replace(/.(?=.{2})/g, "*")}</td>
                            <td className="r num">{won(b.amount)}원</td>
                            <td className="r muted small">{dateTime(b.at)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              </div>
            </div>
          );
        }}
      </Async>
    </div>
  );
}

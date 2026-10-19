import { useState } from "react";
import { cancelBids } from "../../api/admin";
import { getAuction } from "../../api/auction";
import { Async, useAsync } from "../../components/common";
import { dateTime, won } from "../../utils/format";

/** 경매의 비정상 입찰을 골라 취소 (신고 처리 화면, 경매 관리 화면에서 사용) */
export default function BidCancelPanel({ auctionId, onDone }) {
  const state = useAsync(() => getAuction(auctionId), [auctionId]);
  const [picked, setPicked] = useState([]);
  const [reason, setReason] = useState("");
  const [msg, setMsg] = useState(null);

  const toggle = (i) => setPicked(picked.includes(i) ? picked.filter((x) => x !== i) : [...picked, i]);

  async function submit(a) {
    if (!confirm(`선택한 입찰 ${picked.length}건을 취소할까요? 입찰자와 판매자에게 알림이 갑니다.`)) return;
    try {
      const updated = await cancelBids(a.id, picked, reason);
      setMsg({ ok: true, text: `취소했습니다. 현재가가 ${won(updated.current_bid)}원으로 조정되었습니다.` });
      setPicked([]);
      setReason("");
      state.reload();
      onDone?.();
    } catch (e) {
      setMsg({ ok: false, text: e.message });
    }
  }

  return (
    <Async state={state}>
      {(a) => {
        // 지금 남은 입찰만으로 다시 계산했을 때의 현재가 (미리보기)
        const remaining = a.bids.filter((b, i) => !b.cancelled && !picked.includes(i));
        const preview = remaining.length ? Math.max(...remaining.map((b) => b.amount)) : a.start_price;
        return (
          <div style={{ display: "grid", gap: 10 }}>
            <b>입찰 기록 · 경매 #{a.id} {a.title}</b>
            {a.bids.length === 0 ? (
              <p className="muted small" style={{ margin: 0 }}>입찰이 없습니다.</p>
            ) : (
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr><th /><th>입찰자</th><th className="r">입찰가</th><th>시각</th><th>상태</th></tr>
                  </thead>
                  <tbody>
                    {a.bids.map((b, i) => (
                      <tr key={i} className={b.cancelled ? "muted" : ""}>
                        <td>
                          {!b.cancelled && <input type="checkbox" aria-label={`${b.user} ${b.amount}원 입찰 선택`} checked={picked.includes(i)} onChange={() => toggle(i)} />}
                        </td>
                        <td className="small">{b.user}</td>
                        <td className="r num">{won(b.amount)}원</td>
                        <td className="small num">{dateTime(b.at)}</td>
                        <td className="small">{b.cancelled ? <span className="badge" title={b.cancel_reason}>취소됨</span> : <span className="badge green">유효</span>}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {picked.length > 0 && (
              <>
                <input className="input" placeholder="취소 사유 (입찰자에게 알림으로 전달됩니다)" value={reason} onChange={(e) => setReason(e.target.value)} />
                <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
                  <button className="btn sm danger" onClick={() => submit(a)}>선택 입찰 {picked.length}건 취소</button>
                  <span className="muted small">→ 현재가 {won(a.current_bid)}원 → {won(preview)}원</span>
                </div>
              </>
            )}
            {msg && <span className={`hint ${msg.ok ? "ok" : "error"}`}>{msg.text}</span>}
          </div>
        );
      }}
    </Async>
  );
}

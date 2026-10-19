import { useEffect, useState } from "react";
import { submitReport } from "../api/report";
import { REPORT_TYPES } from "../mocks/admin";
import { useAuth } from "./AuthContext";

/** 비정상 경매·입찰자 신고. bidders: 신고 대상으로 고를 수 있는 입찰자 [{id, label(가려진 아이디)}] */
export default function ReportModal({ auction, bidders, onClose }) {
  const { user } = useAuth();
  const [type, setType] = useState("허위매물");
  const [bidder, setBidder] = useState("");
  const [reason, setReason] = useState("");
  const [state, setState] = useState({ busy: false, error: "", done: false });

  useEffect(() => {
    const esc = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [onClose]);

  async function submit(e) {
    e.preventDefault();
    setState({ busy: true, error: "", done: false });
    try {
      await submitReport(user, { type, auction_id: auction.id, auction_title: auction.title, bidder: type === "부정입찰" ? bidder : "", bidder_label: bidders.find((b) => b.id === bidder)?.label, reason });
      setState({ busy: false, error: "", done: true });
    } catch (err) {
      setState({ busy: false, error: err.message, done: false });
    }
  }

  return (
    <div className="modal-back" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <form className="modal" role="dialog" aria-label="신고하기" onSubmit={submit}>
        <h2>🚨 신고하기</h2>
        {state.done ? (
          <>
            <p style={{ margin: 0 }}>신고가 접수되었습니다. 처리 결과는 알림과 마이페이지 › 신고 내역에서 확인할 수 있어요.</p>
            <button type="button" className="btn primary" onClick={onClose}>닫기</button>
          </>
        ) : (
          <>
            <div className="muted small">대상: 경매 #{auction.id} {auction.title}</div>
            {Object.entries(REPORT_TYPES).map(([k, desc]) => (
              <label key={k} className={`radio ${type === k ? "on" : ""}`}>
                <input type="radio" name="type" checked={type === k} onChange={() => setType(k)} />
                <span><b>{k}</b> <span className="muted">— {desc}</span></span>
              </label>
            ))}
            {type === "부정입찰" && bidders.length > 0 && (
              <select className="input" value={bidder} onChange={(e) => setBidder(e.target.value)} aria-label="의심되는 입찰자">
                <option value="">의심되는 입찰자 (선택)</option>
                {bidders.map((b) => <option key={b.id} value={b.id}>{b.label}</option>)}
              </select>
            )}
            <textarea className="input" rows={3} placeholder="어떤 점이 의심되는지 적어주세요 (5자 이상)" value={reason} onChange={(e) => setReason(e.target.value)} />
            {state.error && <span className="hint error">{state.error}</span>}
            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
              <button type="button" className="btn" onClick={onClose}>취소</button>
              <button className="btn primary" disabled={state.busy}>신고 접수</button>
            </div>
            <span className="hint">허위 신고가 반복되면 이용이 제한될 수 있어요.</span>
          </>
        )}
      </form>
    </div>
  );
}

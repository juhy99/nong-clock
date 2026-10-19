import { useState } from "react";
import { BAN_DAYS, activeBan, banText, banUser, liftBan } from "../../api/board";

/** 게시판 이용 제한 걸기/풀기 (게시판 관리·신고 처리 화면에서 사용) */
export default function BanPanel({ userId, name, onDone }) {
  const [days, setDays] = useState(7);
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [, refresh] = useState(0);
  const ban = activeBan(userId);

  async function run(fn) {
    setError("");
    try {
      await fn();
      setReason("");
      refresh((n) => n + 1);
      onDone?.();
    } catch (e) {
      setError(e.message);
    }
  }

  if (ban)
    return (
      <div className="ban-panel">
        <span className="badge red">게시판 이용 제한 중</span>
        <span className="small">{name} · {banText(ban)} · 사유: {ban.reason}</span>
        <button className="btn sm" onClick={() => run(() => liftBan(userId))}>제한 풀기</button>
      </div>
    );
  return (
    <div className="ban-panel">
      <span className="small"><b>{name}</b> 게시판 이용 제한</span>
      <select className="input" value={days ?? ""} onChange={(e) => setDays(e.target.value ? Number(e.target.value) : null)} aria-label="제한 기간">
        {BAN_DAYS.map((d) => <option key={d ?? "forever"} value={d ?? ""}>{d ? `${d}일` : "영구"}</option>)}
      </select>
      <input className="input" placeholder="제한 사유 (회원에게 전달됨)" value={reason} onChange={(e) => setReason(e.target.value)} />
      <button className="btn sm danger" onClick={() => confirm(`${name} 님의 글·댓글 작성을 제한할까요?`) && run(() => banUser(userId, days, reason))}>제한하기</button>
      {error && <span className="hint error">{error}</span>}
    </div>
  );
}

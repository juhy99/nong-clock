import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { POLL_MS, getNotifications, getUnreadCount, markRead, onNotificationsChanged } from "../api/notify";
import { NOTIFY_TYPES } from "../mocks/notifications";
import { dateTime } from "../utils/format";

/** "5분 전" 같은 상대 시간 */
export function ago(iso) {
  const m = Math.floor((Date.now() - new Date(iso)) / 60000);
  if (m < 1) return "방금";
  if (m < 60) return `${m}분 전`;
  if (m < 24 * 60) return `${Math.floor(m / 60)}시간 전`;
  if (m < 7 * 24 * 60) return `${Math.floor(m / 1440)}일 전`;
  return dateTime(iso);
}

/** 알림 한 줄 (종 드롭다운과 마이페이지 알림 탭이 같이 쓴다) */
export function NotificationItem({ n, onOpen }) {
  return (
    <button className={`noti-item ${n.read ? "" : "unread"}`} onClick={() => onOpen(n)}>
      <span className="noti-icon">{NOTIFY_TYPES[n.type]?.icon ?? "🔔"}</span>
      <span>
        <b>{n.title}</b> — {n.body}
        <span className="muted small" style={{ display: "block" }}>{ago(n.at)}</span>
      </span>
    </button>
  );
}

export default function NotificationBell({ user }) {
  const [count, setCount] = useState(0);
  const [open, setOpen] = useState(false);
  const [list, setList] = useState(null);
  const box = useRef(null);
  const nav = useNavigate();

  const refresh = useCallback(() => {
    getUnreadCount(user.id).then(setCount);
    if (open) getNotifications(user.id).then((rows) => setList(rows.slice(0, 6)));
  }, [user.id, open]);

  // 30초마다 안 읽은 알림 수 확인 + 같은 브라우저에서 알림이 생기면 바로 갱신
  useEffect(() => {
    refresh();
    const t = setInterval(refresh, POLL_MS);
    const off = onNotificationsChanged(refresh);
    return () => {
      clearInterval(t);
      off();
    };
  }, [refresh]);

  // 바깥을 누르면 닫기
  useEffect(() => {
    if (!open) return;
    const close = (e) => box.current && !box.current.contains(e.target) && setOpen(false);
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  async function openItem(n) {
    if (!n.read) await markRead(user.id, n.id);
    setOpen(false);
    if (n.link) nav(n.link);
  }

  return (
    <div className="bell" ref={box}>
      <button className="icon-btn" aria-label={`알림 ${count}개`} onClick={() => setOpen(!open)}>
        🔔{count > 0 && <span className="cnt">{count > 99 ? "99+" : count}</span>}
      </button>
      {open && (
        <div className="noti-panel">
          <div className="noti-head">
            <b>알림</b>
            {count > 0 && <button className="link" onClick={() => markRead(user.id)}>모두 읽음</button>}
          </div>
          {list === null ? (
            <div className="state">불러오는 중…</div>
          ) : list.length === 0 ? (
            <div className="state">새 알림이 없습니다</div>
          ) : (
            list.map((n) => <NotificationItem key={n.id} n={n} onOpen={openItem} />)
          )}
          <div className="noti-foot">
            <Link className="link small" to="/mypage?tab=notifications" onClick={() => setOpen(false)}>전체 보기</Link>
            <Link className="link small" to="/mypage?tab=profile" onClick={() => setOpen(false)}>알림 설정</Link>
          </div>
        </div>
      )}
    </div>
  );
}

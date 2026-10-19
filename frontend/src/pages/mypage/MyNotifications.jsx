import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { getNotifications, markRead, onNotificationsChanged } from "../../api/notify";
import { useAuth } from "../../components/AuthContext";
import { Async, SectionHead, useAsync } from "../../components/common";
import { NotificationItem } from "../../components/NotificationBell";

export default function MyNotifications() {
  const { user } = useAuth();
  const nav = useNavigate();
  const state = useAsync(() => getNotifications(user.id), [user.id]);
  useEffect(() => onNotificationsChanged(state.reload), [state.reload]);

  async function open(n) {
    if (!n.read) await markRead(user.id, n.id);
    if (n.link) nav(n.link);
  }

  return (
    <section className="card" style={{ paddingBottom: 8 }}>
      <SectionHead
        title="알림"
        desc="경매·입찰, 이상기후, 공지, 신고 처리 결과 · 받을 종류는 내 정보에서 고를 수 있어요"
        right={<button className="link" onClick={() => markRead(user.id)}>모두 읽음</button>}
      />
      <Async state={state} empty="받은 알림이 없습니다">
        {(rows) => <div style={{ margin: "0 -22px" }}>{rows.map((n) => <NotificationItem key={n.id} n={n} onOpen={open} />)}</div>}
      </Async>
    </section>
  );
}

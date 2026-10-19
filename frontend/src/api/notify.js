// 알림 (Spring 담당). 지금은 브라우저에 저장되는 가짜 데이터로 동작한다.
// 실제로는 입찰·신고 처리·공지 등록 같은 일이 일어날 때 Spring 이 알림 테이블에 한 줄씩 넣고,
// 화면은 30초마다 "안 읽은 알림 수"를 물어본다(폴링). 실시간 푸시(WebSocket)는 필요해지면 그때 붙인다.
import { fake } from "./client";
import { DEFAULT_NOTIFY, notificationsDb } from "../mocks/notifications";
import { usersDb } from "../mocks/auctions";

export const POLL_MS = 30_000;

// 같은 브라우저 안에서 알림이 생기면 종 아이콘을 바로 갱신하기 위한 구독
const listeners = new Set();
export function onNotificationsChanged(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}
const changed = () => listeners.forEach((fn) => fn());

const newestFirst = (a, b) => new Date(b.at) - new Date(a.at);

export const getNotifications = (userId) =>
  fake(notificationsDb.all().filter((n) => n.user === userId).sort(newestFirst), 120);

export const getUnreadCount = (userId) =>
  fake(notificationsDb.all().filter((n) => n.user === userId && !n.read).length, 50);

export function markRead(userId, id) {
  notificationsDb.saveAll(notificationsDb.all().map((n) => (n.user === userId && (id == null || n.id === id) ? { ...n, read: true } : n)));
  changed();
  return fake(true, 50);
}

/**
 * 알림 보내기. 실제로는 Spring 내부에서만 호출된다(화면이 직접 부르지 않음).
 * 받는 사람이 그 종류의 알림을 꺼 두었거나 탈퇴했으면 보내지 않는다.
 * @param {string|string[]} userIds
 * @param {{type: "auction"|"weather"|"notice"|"report", title: string, body: string, link?: string}} n
 */
export function notify(userIds, n) {
  const users = usersDb.all();
  const rows = notificationsDb.all();
  let id = Math.max(0, ...rows.map((r) => r.id));
  for (const uid of new Set([userIds].flat())) {
    const u = users.find((x) => x.id === uid);
    if (!u || u.status === "탈퇴") continue;
    if ((u.notify ?? DEFAULT_NOTIFY)[n.type] === false) continue;
    rows.push({ id: ++id, user: uid, read: false, at: new Date().toISOString(), link: "", ...n });
  }
  notificationsDb.saveAll(rows);
  changed();
}

/** 모든 정상 회원에게 (공지용) */
export function notifyAll(n) {
  notify(usersDb.all().filter((u) => u.status === "정상").map((u) => u.id), n);
}

// 알림 가짜 데이터 (Spring 담당 API 가 생기기 전까지 사용).
import { load, save } from "./store";

const ago = (h) => new Date(Date.now() - h * 3600 * 1000).toISOString();

/** 알림 종류. 회원은 내 정보에서 종류별로 받기/끄기를 고른다. */
export const NOTIFY_TYPES = {
  auction: { label: "경매·입찰", icon: "🔨" },
  comment: { label: "댓글·답글", icon: "💬" },
  weather: { label: "이상기후 주의", icon: "🌧️" },
  notice: { label: "공지사항", icon: "📢" },
  // 신고 처리 결과(report)는 신고 기능을 뺐으므로 없음 (11-11)
};

export const DEFAULT_NOTIFY = Object.fromEntries(Object.keys(NOTIFY_TYPES).map((k) => [k, true]));

const INITIAL = [
  { user: "buyer1", type: "auction", title: "입찰 상회", body: "'해남 월동배추 10kg × 20망'에 더 높은 입찰이 들어왔어요.", link: "/auctions/2", at: ago(0.2) },
  { user: "buyer1", type: "weather", title: "이상기후 주의", body: "다음 주 엽채류(배추·양배추) 예측 오차가 커질 수 있어요. 집중호우 예보가 있습니다.", link: "/ai?item=napa_cabbage", at: ago(1.5) },
  { user: "buyer1", type: "notice", title: "공지", body: "10/25(일) 02:00~04:00 정기 점검이 있어요.", link: "/", at: ago(30), read: true },
  { user: "seller1", type: "auction", title: "새 입찰", body: "'논산 설향 딸기 특품 2kg × 5박스'에 148,000원 입찰이 들어왔어요.", link: "/auctions/1", at: ago(0.5) },
  { user: "seller1", type: "weather", title: "이상기후 주의", body: "다음 주 감자 예측 오차가 커질 수 있어요. 한파 특보 가능성이 있습니다.", link: "/ai?item=potato", at: ago(3) },
].map((n, i) => ({ id: i + 1, read: false, ...n }));

export const notificationsDb = {
  all: () => load("notifications", INITIAL),
  saveAll: (rows) => save("notifications", rows),
};

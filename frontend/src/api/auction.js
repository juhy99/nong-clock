// 경매 (Spring 담당). 지금은 브라우저에 저장되는 가짜 데이터로 동작한다.
// 입찰 규칙 검사는 실제로는 반드시 Spring(서버)에서 해야 한다. 여기서는 화면 흐름 확인용.
import { fake } from "./client";
import { MIN_INCREMENT, auctionsDb } from "../mocks/auctions";

export { MIN_INCREMENT };

const isLive = (a) => a.status === "진행중" && new Date(a.ends_at) > new Date();

/** @param {{sort?: "ending"|"popular"|"price", liveOnly?: boolean}} opts */
export function getAuctions({ sort = "popular", liveOnly = true } = {}) {
  let rows = auctionsDb.all();
  if (liveOnly) rows = rows.filter(isLive);
  const by = {
    ending: (a, b) => new Date(a.ends_at) - new Date(b.ends_at),
    popular: (a, b) => b.bid_count - a.bid_count,
    price: (a, b) => b.current_bid - a.current_bid,
  }[sort];
  return fake(rows.sort(by).map(({ bids, ...rest }) => rest));
}

export function getAuction(id) {
  const a = auctionsDb.all().find((x) => x.id === Number(id));
  if (!a) return Promise.reject(new Error("경매를 찾을 수 없습니다"));
  return fake(a);
}

export function placeBid(id, user, amount) {
  const rows = auctionsDb.all();
  const a = rows.find((x) => x.id === Number(id));
  if (!user) return Promise.reject(new Error("로그인 후 입찰할 수 있습니다"));
  if (!a || !isLive(a)) return Promise.reject(new Error("진행 중인 경매가 아닙니다"));
  if (a.seller === user.id) return Promise.reject(new Error("본인 상품에는 입찰할 수 없습니다"));
  const min = a.bid_count === 0 ? a.start_price : a.current_bid + MIN_INCREMENT;
  if (amount < min) return Promise.reject(new Error(`${min.toLocaleString()}원 이상 입찰해야 합니다`));
  a.current_bid = amount;
  a.bid_count += 1;
  a.bids.push({ user: user.id, amount, at: new Date().toISOString() });
  auctionsDb.saveAll(rows);
  return fake(a);
}

export function getMyBids(userId) {
  const rows = auctionsDb.all()
    .filter((a) => a.bids.some((b) => b.user === userId))
    .map((a) => {
      const mine = Math.max(...a.bids.filter((b) => b.user === userId).map((b) => b.amount));
      return { id: a.id, title: a.title, my_bid: mine, current_bid: a.current_bid, leading: mine === a.current_bid, ends_at: a.ends_at, status: a.status };
    });
  return fake(rows);
}

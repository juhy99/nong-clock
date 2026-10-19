// 경매 (Spring 담당). 지금은 브라우저에 저장되는 가짜 데이터로 동작한다.
// 입찰 규칙 검사는 실제로는 반드시 Spring(서버)에서 해야 한다. 여기서는 화면 흐름 확인용.
import { fake } from "./client";
import { notify } from "./notify";
import { MIN_INCREMENT, auctionsDb } from "../mocks/auctions";
import { won } from "../utils/format";

export { MIN_INCREMENT };

const isLive = (a) => a.status === "진행중" && new Date(a.ends_at) > new Date();

/** 관리자가 취소한 입찰은 기록에는 남기되 가격 계산에서는 뺀다 */
export const validBids = (a) => a.bids.filter((b) => !b.cancelled);

/** 남은 입찰로 현재가·입찰 수를 다시 계산 (입찰 취소 후) */
export function recalc(a) {
  const bids = validBids(a);
  a.bid_count = bids.length;
  a.current_bid = bids.length ? Math.max(...bids.map((b) => b.amount)) : a.start_price;
  return a;
}

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
  const prevLeader = a.bid_count ? validBids(a).find((b) => b.amount === a.current_bid)?.user : null;
  a.current_bid = amount;
  a.bid_count += 1;
  a.bids.push({ user: user.id, amount, at: new Date().toISOString() });
  auctionsDb.saveAll(rows);

  const link = `/auctions/${a.id}`;
  notify(a.seller, { type: "auction", title: "새 입찰", body: `'${a.title}'에 ${won(amount)}원 입찰이 들어왔어요.`, link });
  if (prevLeader && prevLeader !== user.id)
    notify(prevLeader, { type: "auction", title: "입찰 상회", body: `'${a.title}'에 더 높은 입찰(${won(amount)}원)이 들어왔어요.`, link });
  return fake(a);
}

export function getMyBids(userId) {
  const rows = auctionsDb.all()
    .filter((a) => validBids(a).some((b) => b.user === userId))
    .map((a) => {
      const mine = Math.max(...validBids(a).filter((b) => b.user === userId).map((b) => b.amount));
      return { id: a.id, title: a.title, emoji: a.emoji, my_bid: mine, current_bid: a.current_bid, leading: mine === a.current_bid, ends_at: a.ends_at, status: a.status };
    });
  return fake(rows);
}

// ── 판매자: 내 경매 등록·현황 ──

export const AUCTION_DAYS = [1, 3, 5, 7];

/** 판매자가 등록한 경매 (최근 등록 순) */
export const getMyAuctions = (userId) =>
  fake(auctionsDb.all().filter((a) => a.seller === userId).sort((a, b) => b.id - a.id).map(({ bids, ...rest }) => rest));

/**
 * 경매 등록. 관리자 승인 후 경매 마켓에 노출된다(status: 승인대기).
 * @param {{item: string|null, emoji: string, title: string, origin: string, weight_kg: number, start_price: number, days: number, description: string, images: string[]}} form
 *   images: uploadImages 로 받은 사진 주소 (첫 번째가 대표 사진)
 */
export function createAuction(user, form) {
  if (user?.type !== "seller") return Promise.reject(new Error("판매자(농가) 회원만 경매를 등록할 수 있습니다"));
  const rows = auctionsDb.all();
  const a = {
    id: Math.max(0, ...rows.map((x) => x.id)) + 1,
    title: form.title.trim(),
    emoji: form.emoji,
    item: form.item,
    origin: form.origin.trim(),
    weight_kg: form.weight_kg,
    start_price: form.start_price,
    current_bid: form.start_price,
    bid_count: 0,
    ends_at: new Date(Date.now() + form.days * 86400 * 1000).toISOString(),
    seller: user.id,
    status: "승인대기",
    description: form.description.trim(),
    images: form.images ?? [],
    bids: [],
    created_at: new Date().toISOString(),
  };
  rows.push(a);
  auctionsDb.saveAll(rows);
  return fake(a);
}

/** 판매자 본인 경매 취소. 입찰이 하나라도 있으면 취소할 수 없다(입찰자 보호). */
export function cancelMyAuction(user, id) {
  const rows = auctionsDb.all();
  const a = rows.find((x) => x.id === id);
  if (!a || a.seller !== user.id) return Promise.reject(new Error("본인 경매만 취소할 수 있습니다"));
  if (a.bid_count > 0) return Promise.reject(new Error("입찰이 들어온 경매는 취소할 수 없습니다. 고객센터에 문의하세요"));
  a.status = "취소";
  auctionsDb.saveAll(rows);
  return fake(a);
}

/** 화면에 보여줄 상태. 마감 시각이 지난 진행중 경매는 입찰 유무로 낙찰/유찰을 나눈다. */
export function displayStatus(a, now = Date.now()) {
  if (a.status !== "진행중") return a.status;
  if (new Date(a.ends_at) > now) return "진행중";
  return a.bid_count ? "낙찰" : "유찰";
}

export const STATUS_BADGE = { 진행중: "green", 승인대기: "amber", 낙찰: "blue", 유찰: "", 중단: "red", 취소: "" };

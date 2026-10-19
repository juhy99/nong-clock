// 경매·회원 가짜 데이터 (Spring 담당 API 가 생기기 전까지 사용).
import { load, save } from "./store";

const H = 3600 * 1000;

function initialAuctions() {
  const now = Date.now();
  const rows = [
    ["논산 설향 딸기 특품 2kg × 5박스", "🍓", null, "충남 논산", 10, 120000, 148000, 3, 5 * H, "seller1"],
    ["해남 월동배추 10kg × 20망 (산지직송)", "🥬", "napa_cabbage", "전남 해남", 200, 150000, 236000, 6, 26 * H, "seller1"],
    ["청양 고추 10kg 상자 · 스마트팜 재배", "🌶️", null, "충남 청양", 10, 40000, 56500, 2, 1.2 * H, "seller2"],
    ["대저 짭짤이 토마토 5kg × 4", "🍅", "tomato", "부산 대저", 20, 72000, 72000, 0, 50 * H, "seller2"],
    ["수경재배 청상추 4kg", "🥗", null, "경기 이천", 4, 12000, 16800, 4, 9 * H, "seller1"],
    ["제주 노지 감귤 10kg × 3", "🍊", "mandarin", "제주 서귀포", 30, 90000, 118000, 5, 30 * H, "seller2"],
    ["강원 고랭지 감자 20kg", "🥔", "potato", "강원 평창", 20, 25000, 31000, 3, 70 * H, "seller1"],
    ["무안 햇양파 15kg × 10망", "🧅", "onion", "전남 무안", 150, 150000, 0, 0, 96 * H, "seller2"],
  ];
  return rows.map(([title, emoji, item, origin, weight_kg, start_price, current_bid, bid_count, endsIn, seller], i) => ({
    id: i + 1,
    title,
    emoji,
    item, // 예측 품목 코드 (16개 품목이 아니면 null)
    origin,
    weight_kg,
    start_price,
    current_bid: current_bid || start_price,
    bid_count,
    ends_at: new Date(now + endsIn).toISOString(),
    seller,
    status: i === 7 ? "승인대기" : "진행중",
    description: `${origin}에서 직접 출하하는 상품입니다. 수확 후 24시간 이내 발송합니다. (데모 데이터)`,
    bids: Array.from({ length: bid_count }, (_, k) => ({
      user: `buyer${(k % 3) + 1}`,
      amount: Math.round(start_price + ((current_bid - start_price) * (k + 1)) / bid_count),
      at: new Date(now - (bid_count - k) * 0.7 * H).toISOString(),
    })),
  }));
}

export const MIN_INCREMENT = 1000;

export const auctionsDb = {
  all: () => load("auctions", initialAuctions()),
  saveAll: (rows) => save("auctions", rows),
};

const INITIAL_USERS = [
  { id: "admin", email: "admin@farmbid.kr", password: "admin1234", name: "관리자", phone: "010-0000-0000", type: "admin", region: "서울", status: "정상", joined: "2026-10-01" },
  { id: "buyer1", email: "user@farmbid.kr", password: "user1234", name: "김구매", phone: "010-1111-2222", type: "buyer", region: "경기", status: "정상", joined: "2026-10-03" },
  { id: "seller1", email: "farmer@farmbid.kr", password: "farmer1234", name: "박농부", phone: "010-3333-4444", type: "seller", region: "충남", status: "정상", joined: "2026-10-04" },
  { id: "seller2", email: "farm2@farmbid.kr", password: "farm1234", name: "이농장", phone: "010-5555-6666", type: "seller", region: "전남", status: "정상", joined: "2026-10-06" },
  { id: "buyer2", email: "buyer2@farmbid.kr", password: "buyer1234", name: "정구매", phone: "010-7777-8888", type: "buyer", region: "부산", status: "정지", joined: "2026-10-08" },
];

export const usersDb = {
  all: () => load("users", INITIAL_USERS),
  saveAll: (rows) => save("users", rows),
};

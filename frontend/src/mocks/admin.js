// 개발자(관리자) 페이지 가짜 데이터.
const ago = (h) => new Date(Date.now() - h * 3600 * 1000).toISOString();

export const INITIAL_REPORTS = [
  { id: 101, type: "허위매물", target: "경매 #3 청양 고추 10kg", auction_id: 3, reporter: "buyer1", reason: "사진과 실제 상품 상태가 다르다는 후기가 있습니다.", status: "접수", created_at: ago(2), memo: "" },
  { id: 102, type: "부정입찰", target: "경매 #2 해남 월동배추", auction_id: 2, reporter: "seller1", reason: "같은 사람이 여러 계정으로 가격을 올리는 것 같습니다.", status: "검토중", created_at: ago(20), memo: "IP 중복 확인 중" },
  { id: 103, type: "사기의심", target: "회원 buyer2", reporter: "seller2", reason: "낙찰 후 입금하지 않고 연락이 두절되었습니다.", status: "처리완료", created_at: ago(70), memo: "계정 이용정지 처리" },
  { id: 104, type: "허위매물", target: "경매 #5 수경재배 청상추", auction_id: 5, reporter: "buyer2", reason: "원산지 표기가 의심됩니다.", status: "반려", created_at: ago(96), memo: "판매자 증빙 확인, 문제 없음" },
];

export const INITIAL_NOTICES = [
  { id: 1, category: "가격 급등 안내", title: "[농업기상특보] 강원·경북 북부 서리 주의보", body: "새벽 최저 -1℃. 엽채류 노지 재배지 보온 조치 필요. 배추·상추 가격 상승 가능성.", pinned: true, show_on_home: true, created_at: ago(5) },
  { id: 2, category: "서비스 점검", title: "10/25(일) 02:00~04:00 정기 점검", body: "점검 시간에는 경매 입찰과 AI 예측이 일시 중단됩니다.", pinned: false, show_on_home: false, created_at: ago(30) },
  { id: 3, category: "정책 공지", title: "경매 최소 입찰 단위 1,000원 적용", body: "공정한 경매를 위해 최소 입찰 단위를 1,000원으로 정했습니다.", pinned: false, show_on_home: false, created_at: ago(120) },
];

export const NOTICE_CATEGORIES = ["서비스 점검", "가격 급등 안내", "정책 공지", "일반"];
export const REPORT_STATUSES = ["접수", "검토중", "처리완료", "반려"];

/** 신고 유형. 회원 신고 화면과 관리자 화면이 같이 쓴다. 경매용과 게시판(글·댓글)용이 다르다. */
export const BOARD_REPORT_TYPES = {
  "욕설·비방": "욕설, 인신공격, 차별 표현",
  "스팸·광고": "도배, 홍보, 외부 거래 유도",
  "개인정보 노출": "전화번호·주소 등 남의 정보",
  "허위 정보": "사실이 아닌 시세·거래 정보",
  기타: "그 밖의 문제",
};

export const AUCTION_REPORT_TYPES = {
  허위매물: "사진·설명과 실제 상품이 다름",
  사기의심: "외부 거래 유도, 낙찰 후 연락 두절 등",
  부정입찰: "가격 띄우기, 여러 계정으로 입찰 등 비정상 입찰",
  기타: "그 밖의 문제",
};

// 데이터 수집 현황. 실제로는 수집 스크립트가 DB 에 남긴 기록을 Spring/ML API 가 돌려준다.
/**
 * 데이터 원천 목록 (관리자 › 데이터 수집). news 줄은 서버 수집 기록으로 채운다 (api/admin.js getCollectionStatus).
 * mode: server(서버 수집기가 모음) · test(테스트 모드에서 화면이 그때그때 부름) · file(받은 파일) · none(미연결)
 * ranges: 보유 기간 [[시작, 끝], …] (끝 null = 오늘까지), 막대로 그린다. 기간을 모르면 rangeText 만
 */
export const DATA_SOURCES = [
  { key: "news", source: "농업 뉴스", provider: "NAVER API HUB 뉴스 검색", schedule: "1시간마다", mode: "server", note: "collector/news · 90일 보관" },
  {
    key: "market", source: "도매시장 32곳 일별 시세", provider: "팀 데이터 (CSV)", schedule: "받은 파일", mode: "file",
    ranges: [["2020-01-01", "2025-02-28"], ["2025-05-01", "2025-09-30"], ["2026-04-01", "2026-08-31"]],
    note: "빈 기간 2025-03~04, 2025-10~2026-03 · 등급·출하지역·소매가 없음",
  },
  { key: "auction", source: "도매시장 실시간 경락", provider: "aT 공영도매시장", schedule: "-", mode: "none", note: "시세 담당 결정 후 연결" },
  { key: "forecast", source: "단기예보 (기온·강수확률·습도·풍속)", provider: "기상청", schedule: "화면을 열 때", mode: "test", rangeText: "오늘~모레", note: "테스트 모드에서만 · 서버 수집기 개발 전" },
  { key: "warning", source: "기상특보", provider: "기상청", schedule: "화면을 열 때", mode: "test", rangeText: "지금 발효 중", note: "테스트 모드에서만" },
  { key: "asos", source: "ASOS 일자료 (지난 날씨)", provider: "기상청", schedule: "-", mode: "none", note: "키 승인됨 · 수집기 개발 전 (이상기후 판단·모델 학습용)" },
  { key: "agro", source: "농업기상 관측 (지온)", provider: "농촌진흥청", schedule: "-", mode: "none", note: "키 승인됨 · 홈 날씨 '지온' 채울 예정" },
  { key: "holiday", source: "명절·공휴일", provider: "천문연 특일 정보", schedule: "연 1회", mode: "file", rangeText: "2029년까지", note: "holidays.csv 695건 (모델 학습용)" },
];

// 모델 성능: 팀원 모델 v1 결과(v1_화면용_예측.csv)의 과거적중% (7일·2주·1개월)
export const MODEL_PERFORMANCE = {
  model_version: "v1 (팀원 테스트)",
  target: 85,
  rows: [
    ["potato", 85.9, 79.6, 87.0], ["onion", 86.9, 74.0, 71.0], ["carrot", 79.4, 61.2, 60.9],
    ["apple", 72.1, 60.7, 59.4], ["watermelon", 74.4, 57.7, 47.8], ["napa_cabbage", 70.2, 54.5, 47.8],
    ["radish", 69.9, 55.3, 52.2], ["tomato", 51.0, 45.4, 44.9], ["cabbage", 54.6, 41.3, 31.9],
    ["sweet_potato", 94.9, 88.8, 84.1], ["button_mushroom", 71.5, 64.6, 72.5], ["pear", 82.6, 66.3, 62.3],
    ["king_oyster_mushroom", 79.8, 67.4, 69.6], ["green_onion", 66.1, 50.8, 56.5], ["mandarin", 79.7, 75.9, 78.8],
    ["enoki_mushroom", 64.5, 53.5, 53.6],
  ].map(([item, h7, h14, h30]) => ({ item, accuracy: { 7: h7, 14: h14, 30: h30 } })),
};

// 개발자(관리자) 페이지 가짜 데이터.
const ago = (h) => new Date(Date.now() - h * 3600 * 1000).toISOString();

export const INITIAL_REPORTS = [
  { id: 101, type: "허위매물", target: "경매 #3 청양 고추 10kg", auction_id: 3, reporter: "buyer1", reason: "사진과 실제 상품 상태가 다르다는 후기가 있습니다.", status: "접수", created_at: ago(2), memo: "" },
  { id: 102, type: "부정입찰", target: "경매 #2 해남 월동배추", auction_id: 2, reporter: "seller1", reason: "같은 사람이 여러 계정으로 가격을 올리는 것 같습니다.", status: "검토중", created_at: ago(20), memo: "IP 중복 확인 중" },
  { id: 103, type: "사기의심", target: "회원 buyer2", reporter: "seller2", reason: "낙찰 후 입금하지 않고 연락이 두절되었습니다.", status: "처리완료", created_at: ago(70), memo: "회원에게 주의 안내" },
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
 * 데이터 원천 목록 (관리자 › 데이터 수집). news 줄은 뉴스 수집 기록, 날씨 줄(forecast·weather_obs·longrange)은 날씨 수집기 기록·화면 파일로 채운다 (api/admin.js getCollectionStatus).
 * mode: server(서버 수집기가 모음) · live(화면을 열 때 Spring 이 기상청에서 바로 받음) · file(받은 자료를 DB·파일로) · none(미연결)
 * ranges: 보유 기간 [[시작, 끝], …] (끝 null = 오늘까지), 막대로 그린다. 기간을 모르면 rangeText 만
 */
export const DATA_SOURCES = [
  { key: "news", source: "농업 뉴스", provider: "NAVER API HUB 뉴스 검색", schedule: "1시간마다", mode: "server", note: "collector/news · 90일 보관" },
  // 11-17: 예전 설명(빈 기간 2025-03~04 · 2025-10~2026-03, 등급·소매가 없음)은 옛 CSV 기준 → 지금 DB 기준으로. 끝 날짜는 /api/prices/today 의 기준일로 채움
  {
    key: "market", source: "도매시장 32곳 일별 시세", provider: "공영도매시장 경매 자료 → DB (price_daily · 품종 단위 price_unit_daily)", schedule: "받은 자료를 DB에 넣음", mode: "file",
    note: "금액 ÷ 물량(원/kg) · 품목·품종·등급별 · 시세 화면과 AI 예측이 같이 씀",
  },
  { key: "retail", source: "소매가격", provider: "KAMIS 농산물유통정보 → DB (retail_price_daily)", schedule: "수집 스크립트 (collector/daily)", mode: "file", note: "검색 화면의 '도매가보다 N% 비싸요' · 소매가가 없는 품목도 있어요" },
  { key: "production", source: "생산량·재배면적", provider: "통계청 KOSIS → DB (production_yearly)", schedule: "연 1회", mode: "file", note: "원인 모델 입력 (출하량·재배 면적)" },
  { key: "income", source: "농산물 소득·생산비 조사", provider: "농진청 농산물소득조사 · 통계청 생산비조사 → shared/crops.json", schedule: "연 1회", mode: "file", note: "작물 추천의 10a당 수량·경영비 (최근 3개 해 평균) · 재배 시기는 농사로 재배력" },
  {
    key: "forecast", source: "단기·중기예보", provider: "기상청 · 데이터 담당 수집기 (collector/weather)", schedule: "3시간마다 (02:20~23:20)", mode: "server",
    rangeText: "10/21 17시 발표부터", note: "단기 격자 218곳 · 중기 구역 10·도시 27 · 지난 발표는 다시 못 받음",
  },
  { key: "warning", source: "지금 날씨 · 기상특보", provider: "기상청 초단기실황·특보 → Spring /api/weather/regions", schedule: "화면을 열 때 (10분 캐시)", mode: "live", rangeText: "지금 값만 (보관 안 함)", note: "홈 날씨 카드 위쪽 '지금 날씨'" },
  {
    key: "weather_obs", source: "지난 날씨 (관측 통합)", provider: "기상청 ASOS·AWS + 농진청 농업기상 → 데이터 담당 전처리", schedule: "매일 10:40 수집·전처리", mode: "server",
    note: "날씨_대통합_일별.csv → 홈 날씨 '지난 날씨' (5분마다 확인) · 지온은 아직 없음",
  },
  { key: "longrange", source: "장기전망 (1개월·3개월)", provider: "기상청 날씨누리 PDF", schedule: "매일 확인", mode: "server", note: "평년보다 높음·낮음 확률 · 참고용 (강수 적중 낮음) · 화면 연결 전" },
];


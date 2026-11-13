// 기능 켜고 끄기. 화면·관리자 사이트가 모두 이 파일만 본다.
// 경매: 팀 결정으로 보류(2026-11). 꺼 두면 경매 마켓·상세·등록, 마이페이지 내 경매·입찰 참여,
// 홈·검색의 경매, 경매 알림·신고, 관리자 경매 관리·입찰 취소가 모두 숨겨진다. 코드와 가짜 데이터는 그대로 둔다.
// 다시 켜려면 frontend/.env 에 VITE_ENABLE_AUCTION=true 를 넣고 다시 빌드한다.
export const AUCTION_ENABLED = import.meta.env.VITE_ENABLE_AUCTION === "true";

// 알림: 팀 결정으로 숨김(2026-11-13). 꺼 두면 머리말 🔔 종, 마이페이지 새 알림 · 알림 목록 · 알림 설정,
// 내 정보 수정의 "알림 받기" 가 숨겨진다. 코드·가짜 데이터·관리자 화면은 그대로. 다시 켜려면 VITE_ENABLE_NOTIFY=true
export const NOTIFY_ENABLED = import.meta.env.VITE_ENABLE_NOTIFY === "true";

/** 경매와 관련된 신고인지 (예전 신고는 kind 가 없고 경매 신고였다) */
export const isAuctionReport = (r) => (r.kind ?? "auction") === "auction";

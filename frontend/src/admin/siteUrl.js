// 사용자 사이트 주소. 개발 중에는 같은 서버(localhost:5173)라서 비워 두고,
// 관리자 사이트를 다른 도메인(예: admin.farmbid.kr)에 올리면 .env 의 VITE_SITE_URL 에 사용자 사이트 주소를 넣는다.
export const SITE_URL = (import.meta.env.VITE_SITE_URL || "").replace(/\/$/, "");

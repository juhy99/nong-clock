// 관리자 운영 화면 (11-17) — Spring /api/admin/ops/… · /api/admin/site · /api/admin/news/hidden (모두 관리자 로그인만)
import axios from "axios";

const api = axios.create({ timeout: 20000 });
const call = (req, fallback) =>
  req.then(
    (r) => r.data,
    (e) => {
      const err = new Error(e.response?.data?.message || (e.response ? fallback : "서버에 연결할 수 없습니다"));
      err.status = e.response?.status ?? 0;
      throw err;
    },
  );

/** 자료가 며칠 것까지 들어왔나 */
export const getFreshness = () => call(api.get("/api/admin/ops/freshness"), "자료 상태를 불러오지 못했습니다");
/** 가장 최근 예측 표 점검 */
export const getForecastHealth = () => call(api.get("/api/admin/ops/forecast-health"), "예측 점검을 불러오지 못했습니다");
/** 지난 예측과 실제 비교 */
export const getForecastVsActual = () => call(api.get("/api/admin/ops/forecast-vs-actual"), "예측·실제 비교를 불러오지 못했습니다");
/** 서버 오류 · 요청 제한 · 로그인 실패 기록 */
export const getOpsErrors = () => call(api.get("/api/admin/ops/errors"), "오류 기록을 불러오지 못했습니다");
/** 짧은 시간에 글·댓글을 많이 쓴 회원 */
export const getFlood = () => call(api.get("/api/admin/ops/flood"), "도배 감지를 불러오지 못했습니다");

/** 사이트 설정 (금칙어 포함) */
export const getAdminSite = () => call(api.get("/api/admin/site"), "사이트 설정을 불러오지 못했습니다");
export const saveAdminSite = (patch) => call(api.put("/api/admin/site", patch), "사이트 설정을 저장하지 못했습니다");

/** 숨긴 뉴스 기사 */
export const getHiddenNews = () => call(api.get("/api/admin/news/hidden"), "숨긴 기사를 불러오지 못했습니다");
export const hideNews = (url, title, reason) => call(api.post("/api/admin/news/hidden", { url, title, reason }), "기사를 숨기지 못했습니다");
export const unhideNews = (url) => call(api.delete("/api/admin/news/hidden", { params: { url } }), "기사를 다시 보이게 하지 못했습니다");

/** 평일 기준으로 며칠 지났나 (토·일은 세지 않음 — 도매시장 원장은 평일에 올라옴) */
export function weekdaysSince(iso, today) {
  if (!iso) return null;
  let n = 0;
  const d = new Date(`${iso}T00:00:00`), end = new Date(`${today}T00:00:00`);
  while (d < end) {
    d.setDate(d.getDate() + 1);
    if (d.getDay() !== 0 && d.getDay() !== 6 && d <= end) n++;
  }
  return n;
}

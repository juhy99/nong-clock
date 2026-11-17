// 관리자 데이터 갱신 (11-17) — Spring /api/admin/refresh… → 갱신 서비스(price-updater 컨테이너). 모두 관리자 로그인만
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

export const WOLBO_MAX = 50 * 1024 * 1024;
export const WOLBO_NAME = /^(VC|VS|VPO|F)\d{6}.*\.pdf$/i;

/** 상태: 예측 기준일 · v4 기준월 · 자료별 수집 결과 · 월보 · 실행 중 · 최근 실행 */
export const getRefreshStatus = () => call(api.get("/api/admin/refresh"), "갱신 상태를 불러오지 못했습니다");
/** 갱신 시작 (job = daily | monthly). 바로 돌아오고 진행은 getRefreshStatus 로 확인 */
export const startRefresh = (job) => call(api.post(`/api/admin/refresh/${job}`), "갱신을 시작하지 못했습니다");
/** 월보 PDF 한 개 올리기. 이름·크기는 보내기 전에 먼저 확인 (서버도 다시 확인) */
export function uploadWolbo(file) {
  const fail = (m) => Promise.reject(Object.assign(new Error(m), { status: 400 }));
  if (!WOLBO_NAME.test(file.name)) return fail("월보 파일 이름이 아니에요 (VC·VS·VPO·F + 연월 6자리 .pdf, 예: VC202611.pdf)");
  if (file.size > WOLBO_MAX) return fail("파일이 너무 커요 (50MB 까지)");
  const form = new FormData();
  form.append("file", file);
  return call(api.post("/api/admin/refresh/wolbo", form, { timeout: 180000 }), "파일을 올리지 못했습니다");
}

// 관리자: 서버에 모인 수집 데이터. 뉴스 수집기(collector/news)가 남기는 파일을 그대로 읽는다.
//   collect_log.json 수집 기록 · news-recent.json 최근 7일 기사 · rejected.json 마지막 수집에서 거른 기사
// 서버 화면은 /data/ (nginx), 내 PC 개발은 VITE_NEWS_URL 의 폴더 또는 테스트 모드의 /live/collector-data/.
// 서버 연결이 없으면 예시 데이터(sample: true)를 보여준다.
import { DATA_SOURCE, NEWS_URL, fake } from "./client";
import { sampleNewsCollection } from "../mocks/collection";

/** 수집 파일이 있는 폴더 주소 ("" 이면 서버 연결 없음) */
export const DATA_BASE = NEWS_URL ? NEWS_URL.replace(/\/[^/]*$/, "") : DATA_SOURCE === "live" ? "/live/collector-data" : "";

const LATE_MIN = 120; // 마지막 성공이 이보다 오래되면 "지연"
const DOWN_MIN = 180; // 이보다 오래되면 "멈춤" (대시보드 경고)

async function getJson(name, { optional = false } = {}) {
  const res = await fetch(`${DATA_BASE}/${name}`, { cache: "no-cache" }).catch(() => null);
  if (!res) throw new Error("서버에 연결할 수 없어요 (서버 주소·접속 확인)");
  if (res.status === 404 && optional) return null;
  if (res.status === 404) throw new Error("서버에 아직 수집 기록이 없어요 (수집기가 처음 한 번 돌 때까지 1~2분)");
  if (!res.ok) throw new Error(`수집 기록을 불러오지 못했어요 (HTTP ${res.status})`);
  return res.json();
}

/**
 * 뉴스 수집 현황
 * @returns {Promise<{log: object, recent: object, rejected: object|null, sample: boolean}>}
 */
export async function getNewsCollection() {
  if (!DATA_BASE) return fake(sampleNewsCollection());
  const [log, recent, rejected] = await Promise.all([
    getJson("collect_log.json"),
    getJson("news-recent.json", { optional: true }),
    getJson("rejected.json", { optional: true }),
  ]);
  return { log, recent: recent ?? { articles: [], count: 0 }, rejected, sample: false };
}

const minutesSince = (iso, now) => (iso ? (now - new Date(iso)) / 60000 : Infinity);

/**
 * 수집기 상태 판단 (관리자 대시보드·서버 상태·데이터 수집 화면이 같이 씀)
 * @returns {{level: "ok"|"warn"|"bad", label: string, detail: string, lastSuccessAt: string|null}}
 */
export function newsHealth(log, now = Date.now()) {
  const last = log?.runs?.[0];
  const lastSuccessAt = log?.runs?.find((r) => r.ok)?.finished_at ?? null;
  const since = minutesSince(lastSuccessAt, now);
  const failedInRow = (log?.runs ?? []).findIndex((r) => r.ok);
  const fails = failedInRow === -1 ? (log?.runs ?? []).length : failedInRow;
  if (!last) return { level: "bad", label: "기록 없음", detail: "아직 한 번도 수집하지 않았어요", lastSuccessAt };
  if (since > DOWN_MIN) {
    const why = !last.ok && last.errors?.[0] ? ` · 마지막 오류: ${last.errors[0]}` : "";
    return { level: "bad", label: "멈춤", detail: `${Math.floor(since / 60)}시간째 새 수집이 없어요${why}`, lastSuccessAt };
  }
  if (!last.ok) return { level: "warn", label: "실패", detail: `최근 ${fails}회 연속 실패 · ${last.errors?.[0] ?? ""}`, lastSuccessAt };
  if (since > LATE_MIN) return { level: "warn", label: "지연", detail: `마지막 성공 ${Math.round(since)}분 전`, lastSuccessAt };
  return { level: "ok", label: "정상", detail: `마지막 성공 ${Math.max(0, Math.round(since))}분 전`, lastSuccessAt };
}

/** 서버에 올라간 화면 버전 (배포 스크립트가 빌드할 때 넣음. npm run dev 면 dev) */
export const BUILD = {
  sha: import.meta.env.VITE_BUILD_SHA || "",
  message: import.meta.env.VITE_BUILD_MSG || "",
  committedAt: import.meta.env.VITE_BUILD_TIME || "",
  builtAt: typeof __BUILT_AT__ === "string" ? __BUILT_AT__ : "",
  dev: import.meta.env.DEV,
};

// 화면 표시용 공통 함수. 가격·날짜 표기는 반드시 여기를 거쳐서 팀 규칙(원/kg, 비교 날짜 표기)을 지킨다.

const WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"];

/** 1240 → "1,240" */
export const won = (n) => (n == null ? "-" : Math.round(n).toLocaleString("ko-KR"));

/** 1240 → "1,240원/kg" */
export const wonPerKg = (n) => `${won(n)}원/kg`;

/** "2026-10-16" → "10/16(금)" */
export function shortDate(iso) {
  const d = new Date(`${iso}T00:00:00`);
  return `${d.getMonth() + 1}/${d.getDate()}(${WEEKDAYS[d.getDay()]})`;
}

/** "2026-10-16" → "10/16" */
export const md = (iso) => {
  const d = new Date(`${iso}T00:00:00`);
  return `${d.getMonth() + 1}/${d.getDate()}`;
};

/** "2026-10-19T14:03:00" → "10/19 14:03" */
export function dateTime(iso) {
  const d = new Date(iso);
  const p = (x) => String(x).padStart(2, "0");
  return `${d.getMonth() + 1}/${d.getDate()} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

/** 23.1 → "+23.1%", -5 → "-5.0%" */
export const pct = (n) => `${n > 0 ? "+" : ""}${Number(n).toFixed(1)}%`;

/** 남은 시간(ms) → "1일 02:03:04" */
export function remain(ms) {
  if (ms <= 0) return "마감";
  const s = Math.floor(ms / 1000);
  const d = Math.floor(s / 86400);
  const p = (x) => String(x).padStart(2, "0");
  const hms = `${p(Math.floor((s % 86400) / 3600))}:${p(Math.floor((s % 3600) / 60))}:${p(s % 60)}`;
  return d > 0 ? `${d}일 ${hms}` : hms;
}

export const todayIso = () => new Date().toISOString().slice(0, 10);

export function addDays(iso, n) {
  const d = new Date(`${iso}T00:00:00`);
  d.setDate(d.getDate() + n);
  return d.toISOString().slice(0, 10);
}

/** 문자열 → 고정 난수 (가짜 데이터가 새로고침마다 바뀌지 않게) */
export function seeded(seedText) {
  let h = 2166136261;
  for (const c of String(seedText)) h = Math.imul(h ^ c.charCodeAt(0), 16777619);
  return () => {
    h = Math.imul(h ^ (h >>> 15), 2246822507);
    h = Math.imul(h ^ (h >>> 13), 3266489909);
    return ((h ^= h >>> 16) >>> 0) / 4294967296;
  };
}

/** 회원 지역 (시·도) */
export const SIDO = ["서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"];

/** 010-1234-5678 형태로 자동 하이픈 */
export const formatPhone = (v) => {
  const d = v.replace(/\D/g, "").slice(0, 11);
  if (d.length < 4) return d;
  if (d.length < 8) return `${d.slice(0, 3)}-${d.slice(3)}`;
  return `${d.slice(0, 3)}-${d.slice(3, 7)}-${d.slice(7)}`;
};

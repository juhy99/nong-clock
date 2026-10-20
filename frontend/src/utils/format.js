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

// 날짜는 "사용자 컴퓨터 시간(한국)" 기준으로 만든다. toISOString() 은 UTC 라서 한국 오전 9시 전에는 하루 전 날짜가 나온다.
const localIso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

export const todayIso = () => localIso(new Date());

export function addDays(iso, n) {
  const d = new Date(`${iso}T00:00:00`);
  d.setDate(d.getDate() + n);
  return localIso(d);
}

/** 두 날짜("YYYY-MM-DD") 사이 일수 */
export const daysBetween = (from, to) => Math.round((new Date(`${to}T00:00:00`) - new Date(`${from}T00:00:00`)) / 86400000);

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

/** 게시판 작성일: 오늘 쓴 글은 "14:03", 그 전은 "2026-10-18" */
export function boardDate(iso) {
  const d = new Date(iso);
  const now = new Date();
  const p = (x) => String(x).padStart(2, "0");
  if (d.toDateString() === now.toDateString()) return `${p(d.getHours())}:${p(d.getMinutes())}`;
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

/** 뉴스 시각: "32분 전", "5시간 전", "어제", "3일 전", 일주일 넘으면 "10/12" */
export function timeAgo(iso, now = Date.now()) {
  const min = Math.floor((now - new Date(iso)) / 60000);
  if (min < 1) return "방금";
  if (min < 60) return `${min}분 전`;
  const h = Math.floor(min / 60);
  const d = new Date(iso);
  const today = new Date(now);
  const yesterday = new Date(now - 86400000);
  if (d.toDateString() === today.toDateString()) return `${h}시간 전`;
  if (d.toDateString() === yesterday.toDateString()) return "어제";
  const days = Math.floor(h / 24);
  return days < 7 ? `${days}일 전` : `${d.getMonth() + 1}/${d.getDate()}`;
}

/** 뉴스 날짜 묶음 제목: "오늘 · 10월 20일 (화)" */
export function dayLabel(iso, now = Date.now()) {
  const d = new Date(iso);
  const text = `${d.getMonth() + 1}월 ${d.getDate()}일 (${WEEKDAYS[d.getDay()]})`;
  if (d.toDateString() === new Date(now).toDateString()) return `오늘 · ${text}`;
  if (d.toDateString() === new Date(now - 86400000).toDateString()) return `어제 · ${text}`;
  return text;
}

/** "14:00" */
export const hourMinute = (iso) => {
  const d = new Date(iso);
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
};

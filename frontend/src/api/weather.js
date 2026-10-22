// 날씨: 서버의 날씨 수집기(collector/weather, 데이터 담당)가 매일 만드는 날씨_대통합_일별.csv 를
// collector/weather_site 가 화면용 JSON 으로 바꾼 것을 읽는다.
//   regions-daily.json 시·도 최근 120일 (+ 그 날의 평년값) · regions-monthly.json 최근 25개월 + 월 평년 · meta.json 만든 시각·기간·오류
//   collect_log.json · preprocess_log.json 수집기 기록 (관리자 › 데이터 수집)
// 서버 화면은 /data/weather/, 내 PC 개발은 VITE_NEWS_URL 과 같은 서버 또는 테스트 모드의 /live/collector-data/weather/.
// 서버 연결이 없으면 예시 데이터(sample: true). 나중에 Spring 이 생기면 이 파일 안쪽만 /api/weather/... 로 바꾼다.
import { fake } from "./client";
import { DATA_BASE } from "./collection";
import { sampleWeatherHistory } from "../mocks/weatherHistory";
import { daysBetween, todayIso } from "../utils/format";

export const WEATHER_BASE = DATA_BASE ? `${DATA_BASE}/weather` : "";

async function getJson(name) {
  const res = await fetch(`${WEATHER_BASE}/${name}`, { cache: "no-cache" }).catch(() => null);
  if (!res) throw new Error("서버에 연결할 수 없어요 (서버 주소·접속 확인)");
  if (res.status === 404) throw new Error("서버에 날씨 파일이 아직 없어요 (날씨 수집기가 첫 전처리를 마치기 전)");
  if (!res.ok) throw new Error(`날씨 파일을 불러오지 못했어요 (HTTP ${res.status})`);
  return res.json();
}

/**
 * 날씨 파일·수집기 상태 (관리자 › 데이터 수집·서버 상태). 기록 파일이 아직 없으면 null
 * @returns {Promise<{meta: object, collect: object|null, preprocess: object|null, sample?: boolean}>}
 */
export async function getWeatherStatus() {
  if (!WEATHER_BASE) return fake({ meta: sampleWeatherHistory().meta, collect: null, preprocess: null, sample: true });
  const optional = (name) => getJson(name).catch((e) => (/아직 없어요/.test(e.message) ? null : Promise.reject(e)));
  const [meta, collect, preprocess] = await Promise.all([
    getJson("meta.json").catch((e) => ({ ok: false, error: e.message, unreachable: true })),
    optional("collect_log.json"),
    optional("preprocess_log.json"),
  ]);
  return { meta, collect, preprocess };
}

// 수집기별 기대 주기: 예보는 3시간마다(24시간 안에 못 받으면 그 발표는 영영 못 받음), 관측·장기전망은 하루 1번
export const COLLECTOR_TIMING = {
  fcst: { lateH: 4, downH: 9 },
  asos: { lateH: 26, downH: 50 },
  aws: { lateH: 26, downH: 50 },
  agri: { lateH: 26, downH: 50 },
  longrange: { lateH: 26, downH: 50 },
  preprocess: { lateH: 26, downH: 50 },
};

/**
 * 날씨 수집기 기록(runs 는 오래된 것부터) → 한 수집기(fcst·asos·…) 또는 전처리(preprocess)의 상태
 * @returns {{level: "ok"|"warn"|"bad", label: string, detail: string, lastRun: string|null, lastOk: string|null}}
 */
export function collectorHealth(log, src, now = Date.now()) {
  const { lateH, downH } = COLLECTOR_TIMING[src];
  const runs = (log?.runs ?? []).filter((r) => src === "preprocess" || r.sources?.[src]);
  const part = (r) => (src === "preprocess" ? r : r.sources[src]);
  const last = runs.at(-1);
  const lastOk = runs.filter((r) => part(r).ok).at(-1);
  if (!last) return { level: "bad", label: "기록 없음", detail: "아직 한 번도 실행하지 않았어요", lastRun: null, lastOk: null };
  const hours = lastOk ? (now - new Date(lastOk.finished_at)) / 3600000 : Infinity;
  const err = part(last).errors?.[0] ?? "";
  const base = { lastRun: last.finished_at, lastOk: lastOk?.finished_at ?? null };
  if (hours > downH)
    return { ...base, level: "bad", label: "멈춤", detail: `${lastOk ? `${Math.floor(hours)}시간째` : "한 번도"} 성공 없음${err ? ` · 마지막 오류: ${err}` : ""}` };
  if (!part(last).ok) return { ...base, level: "warn", label: "실패", detail: err || "마지막 실행 실패 (data/logs 확인)" };
  if (hours > lateH) return { ...base, level: "warn", label: "지연", detail: `마지막 성공 ${Math.floor(hours)}시간 전` };
  const p = part(last);
  return { ...base, level: "ok", label: "정상", detail: `마지막 성공 ${Math.max(0, Math.round(hours * 60))}분 전 · 호출 ${p.calls ?? 0} · 추가 ${p.added ?? 0}` };
}

/** 여러 상태 중 가장 나쁜 것 */
export const worstHealth = (list) => {
  const rank = { bad: 2, warn: 1, ok: 0 };
  return list.filter(Boolean).reduce((a, b) => (rank[b.level] > rank[a.level] ? b : a));
};

/**
 * 지난 날씨 전체 (홈 날씨 지도)
 * @returns {Promise<{daily: object, monthly: object, meta: object, sample: boolean}>}
 */
export async function getWeatherHistory() {
  if (!WEATHER_BASE) return fake(sampleWeatherHistory());
  const [daily, monthly, meta] = await Promise.all([getJson("regions-daily.json"), getJson("regions-monthly.json"), getJson("meta.json")]);
  return { daily, monthly, meta, sample: false };
}

// 관측 기준 주의 신호 (최근 7일). 기준값은 데이터 담당 전처리와 같게: 폭염 33℃ · 영하 0℃ · 강풍 순간 14m/s
const HOT = 33, FROST = 0, GUST = 14, HEAVY_RAIN = 80, DRY_DAYS = 7;
const r1 = (n) => Math.round(n * 10) / 10;
const sum = (xs) => xs.reduce((s, x) => s + x, 0);

/**
 * 한 시·도의 지난 날씨 요약
 * @param {{daily: object, monthly: object}} h getWeatherHistory() 결과
 * @param {string} sido "서울" 같은 약칭 (홈 날씨 지도의 지역 이름과 같음)
 */
export function summarizeRegion(h, sido, today = todayIso()) {
  const rows = h.daily.regions?.[sido] ?? [];
  if (!rows.length) return null;
  const last = rows.at(-1);
  const recent30 = rows.slice(-30);
  const week = rows.slice(-7);

  // 비 안 온 날(1mm 미만)이 며칠째인지. 값이 없는 날을 만나면 멈춘다
  let dry = 0;
  for (let i = rows.length - 1; i >= 0 && rows[i].rain_mm != null && rows[i].rain_mm < 1; i--) dry++;

  const signals = [];
  const count = (f) => week.filter(f).length;
  if (dry >= DRY_DAYS) signals.push({ icon: "🏜️", text: `비 안 온 날 ${dry}일째`, tip: "노지 관수 확인" });
  const heavy = week.filter((d) => (d.rain_mm ?? 0) >= HEAVY_RAIN);
  if (heavy.length) signals.push({ icon: "🌧️", text: `하루 ${HEAVY_RAIN}mm 넘는 비 ${heavy.length}일`, tip: "침수·병해 주의" });
  const frost = count((d) => d.temp_min != null && d.temp_min < FROST);
  if (frost) signals.push({ icon: "🥶", text: `영하로 내려간 날 ${frost}일`, tip: "서리·냉해 주의" });
  const hot = count((d) => d.temp_max != null && d.temp_max >= HOT);
  if (hot) signals.push({ icon: "🥵", text: `${HOT}℃ 넘은 날 ${hot}일`, tip: "고온 피해 주의" });
  const windy = count((d) => d.gust != null && d.gust >= GUST);
  if (windy) signals.push({ icon: "🌬️", text: `강한 바람 ${windy}일`, tip: "시설물 점검" });

  // 최근 7일 평년 대비 (일별 평년값이 있을 때: 서버 수집기 v2 표)
  const wk = week.filter((d) => d.temp_avg != null && d.normal_temp != null);
  const wkRain = week.filter((d) => d.rain_mm != null && d.normal_rain != null);
  const weekVsNormal =
    wk.length >= 5
      ? {
          temp_diff: r1(sum(wk.map((d) => d.temp_avg - d.normal_temp)) / wk.length),
          rain: r1(sum(wkRain.map((d) => d.rain_mm))),
          normal_rain: r1(sum(wkRain.map((d) => d.normal_rain))),
        }
      : null;

  // 지난달(다 끝난 달) 평년 대비. 이번 달은 아직 안 끝나 평년 한 달 값과 비교하면 치우친다
  const lastMonth = h.monthly.regions?.[sido]?.at(-1) ?? null;
  const normal = lastMonth ? h.monthly.normals?.[sido]?.[String(Number(lastMonth.month.slice(5, 7)))] : null;
  const vsNormal =
    lastMonth && normal
      ? {
          month: lastMonth.month,
          temp: lastMonth.temp_avg,
          temp_diff: lastMonth.temp_avg != null && normal.temp_avg != null ? r1(lastMonth.temp_avg - normal.temp_avg) : null,
          rain: lastMonth.rain_mm,
          rain_pct: lastMonth.rain_mm != null && normal.rain_mm ? Math.round((lastMonth.rain_mm / normal.rain_mm) * 100) : null,
        }
      : null;

  return {
    last,
    recent30,
    week_rain: r1(sum(week.map((d) => d.rain_mm ?? 0))),
    dry_days: dry,
    signals,
    vs_normal: vsNormal,
    week_vs_normal: weekVsNormal,
    stale_days: daysBetween(last.date, today) - 1, // 어제 자료까지 있으면 0
  };
}

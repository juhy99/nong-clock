// 테스트 모드(live) 전용: 기상청 단기예보·기상특보를 직접 불러 홈 날씨 지도 모양으로 바꾼다.
// 실제 서비스에서는 수집기가 이 일을 하고 Spring 이 DB에서 읽어 준다. 여기 변환 규칙은 그쪽에 그대로 옮겨 쓰면 된다.
// 주소는 /live/kma/... → Vite 개발 서버가 apis.data.go.kr 로 보내며 serviceKey 를 붙인다 (vite.config.js).
import { liveGet } from "../client";
import { WEATHER_REGIONS } from "../../mocks/weather";

const FCST = "/live/kma/1360000/VilageFcstInfoService_2.0";
const WARN = "/live/kma/1360000/WthrWrnInfoService";

/** 시·도 대표 지점(시·도청 소재지)의 단기예보 격자 (기상청 격자 엑셀 기준) */
const GRID = {
  seoul: [60, 127], busan: [98, 76], daegu: [89, 90], incheon: [55, 124], gwangju: [58, 74], daejeon: [67, 100],
  ulsan: [102, 84], sejong: [66, 103], gyeonggi: [60, 121], gangwon: [73, 134], "north-chungcheong": [69, 106],
  "south-chungcheong": [55, 106], "north-jeolla": [63, 89], "south-jeolla": [51, 67],
  "north-gyeongsang": [91, 106], "south-gyeongsang": [90, 77], jeju: [52, 38],
};

/** 특보 발효현황 글에서 시·도를 찾을 이름 (괄호 안 세부 지역은 지우고 찾는다: "경기도(광주…)" 가 광주광역시로 잡히지 않게) */
const WARN_NAMES = {
  seoul: ["서울"], busan: ["부산"], daegu: ["대구"], incheon: ["인천"], gwangju: ["광주"], daejeon: ["대전"],
  ulsan: ["울산"], sejong: ["세종"], gyeonggi: ["경기"], gangwon: ["강원"], "north-chungcheong": ["충청북도", "충북"],
  "south-chungcheong": ["충청남도", "충남"], "north-jeolla": ["전라북도", "전북"], "south-jeolla": ["전라남도", "전남"],
  "north-gyeongsang": ["경상북도", "경북"], "south-gyeongsang": ["경상남도", "경남"], jeju: ["제주"],
};

const SKY = { 1: ["☀️", "맑음"], 3: ["⛅", "구름 많음"], 4: ["☁️", "흐림"] };
const PTY = { 1: ["🌧️", "비"], 2: ["🌨️", "비/눈"], 3: ["❄️", "눈"], 4: ["🌦️", "소나기"], 5: ["🌧️", "빗방울"], 6: ["🌨️", "빗방울눈날림"], 7: ["❄️", "눈날림"] };

/** 지금 한국 시각을 { date: "20261021", hour: 14, min: 35 } 로 (브라우저 시간대와 상관없이) */
function kstNow(ms = Date.now()) {
  const d = new Date(ms + 9 * 3600000);
  const date = d.toISOString().slice(0, 10).replaceAll("-", "");
  return { date, hour: d.getUTCHours(), min: d.getUTCMinutes() };
}
const pad = (n) => String(n).padStart(2, "0");

/** 초단기실황 발표 시각: 매시 정각 자료가 40분쯤 올라오므로 40분 전 기준 정각 */
function ncstBase() {
  const k = kstNow(Date.now() - 40 * 60000);
  return { base_date: k.date, base_time: `${pad(k.hour)}00` };
}

/** 오늘 최저·최고 기온이 모두 들어 있는 단기예보: 오늘 02시 발표 (02:10 전이면 어제 23시 발표) */
function fcstBase() {
  const now = kstNow();
  if (now.hour > 2 || (now.hour === 2 && now.min >= 10)) return { base_date: now.date, base_time: "0200", today: now.date };
  return { base_date: kstNow(Date.now() - 86400000).date, base_time: "2300", today: now.date };
}

async function kma(path, params) {
  const q = new URLSearchParams({ pageNo: 1, dataType: "JSON", ...params });
  const data = await liveGet(`${path}?${q}`);
  // 키 오류 등은 { OpenAPI_ServiceResponse: { cmmMsgHeader: { returnAuthMsg, errMsg } } } 로 온다
  const err = data?.OpenAPI_ServiceResponse?.cmmMsgHeader;
  if (err) throw new Error(`공공데이터포털: ${err.returnAuthMsg ?? err.errMsg} (${err.errMsg})`);
  const code = data?.response?.header?.resultCode;
  if (code === "03") return []; // NO_DATA
  if (code !== "00") throw new Error(`기상청: ${data?.response?.header?.resultMsg ?? "응답 형식이 다릅니다"}`);
  const item = data.response.body?.items?.item ?? [];
  return Array.isArray(item) ? item : [item];
}

/** 농사 한 줄 조언 (이상기후 감지 규칙의 시작점. 기준값은 팀이 정하면 바꾼다) */
export function farmNote({ min, max, rain_prob, humidity, warning }) {
  if (warning) return `${warning} 발효 중 · 시설물·작물 피해 대비`;
  if (min != null && min <= 0) return "영하 기온 · 서리·냉해 주의, 보온 대비";
  if (max != null && max >= 33) return "고온 · 차광·관수 필요";
  if (rain_prob != null && rain_prob >= 60) return "강수 예보 · 수확 일정 조정 권장";
  if (humidity != null && humidity < 35) return "건조한 날씨 · 노지 관수 필요";
  if (min != null && max != null && max - min >= 12) return "일교차 큼 · 엽채류 냉해 주의";
  return "작물 생육에 무난한 날씨";
}

async function regionWeather(id, ncst, fcst) {
  const [nx, ny] = GRID[id];
  const [now, rows] = await Promise.all([
    kma(`${FCST}/getUltraSrtNcst`, { numOfRows: 20, nx, ny, base_date: ncst.base_date, base_time: ncst.base_time }),
    kma(`${FCST}/getVilageFcst`, { numOfRows: 1000, nx, ny, base_date: fcst.base_date, base_time: fcst.base_time }),
  ]);
  // 관측 결측은 +900 이상·-900 이하로 온다
  const obs = Object.fromEntries(now.map((r) => [r.category, Math.abs(Number(r.obsrValue)) >= 900 ? NaN : Number(r.obsrValue)]));
  const today = rows.filter((r) => r.fcstDate === fcst.today);
  const pick = (cat) => today.find((r) => r.category === cat)?.fcstValue;
  // 지금 이후 가장 가까운 예보 시각의 하늘·강수확률
  const hour = `${pad(kstNow().hour)}00`;
  const at = (cat) => (today.find((r) => r.category === cat && r.fcstTime >= hour) ?? today.filter((r) => r.category === cat).at(-1))?.fcstValue;
  const tmn = pick("TMN"), tmx = pick("TMX");
  const temps = today.filter((r) => r.category === "TMP").map((r) => Number(r.fcstValue));
  const ptyNow = obs.PTY > 0 ? obs.PTY : Number(at("PTY") ?? 0);
  const [icon, sky] = PTY[ptyNow] ?? SKY[Number(at("SKY"))] ?? ["🌤️", "-"];
  return {
    id,
    name: WEATHER_REGIONS[id],
    temp: Number.isFinite(obs.T1H) ? Math.round(obs.T1H) : at("TMP") != null ? Math.round(Number(at("TMP"))) : null,
    min: tmn != null ? Math.round(Number(tmn)) : temps.length ? Math.min(...temps) : null,
    max: tmx != null ? Math.round(Number(tmx)) : temps.length ? Math.max(...temps) : null,
    icon,
    sky,
    rain_prob: at("POP") != null ? Number(at("POP")) : null,
    humidity: Number.isFinite(obs.REH) ? obs.REH : null,
    wind: Number.isFinite(obs.WSD) ? obs.WSD : null,
    soil_temp: null, // 단기예보에는 지온이 없음 → 농진청 농업기상 관측지대 API 로 채울 예정
  };
}

/** 특보 발효현황 → { 지역 id: "강풍주의보" | "강풍주의보 외 1건" } (실패해도 날씨는 보여주도록 빈 값) */
async function warnings() {
  try {
    const rows = await kma(`${WARN}/getPwnStatus`, { numOfRows: 10 });
    const text = rows.map((r) => r.t6 ?? "").join("\n");
    const out = {};
    for (const line of text.split(/\r?\n/)) {
      const m = line.match(/^\s*o\s*([^:]+?)\s*:\s*(.+)$/);
      if (!m) continue;
      const name = m[1].replace(/\s/g, "");
      const areas = m[2].replace(/\([^)]*\)/g, "");
      for (const [id, names] of Object.entries(WARN_NAMES))
        if (names.some((n) => areas.includes(n)) && !out[id]?.includes(name)) (out[id] ??= []).push(name);
    }
    // 여러 개면 "강풍주의보 외 1건"
    return Object.fromEntries(Object.entries(out).map(([id, list]) => [id, list.length > 1 ? `${list[0]} 외 ${list.length - 1}건` : list[0]]));
  } catch (e) {
    console.warn("[테스트 모드] 기상특보를 불러오지 못했습니다:", e.message);
    return {};
  }
}

/** 한 번에 4곳씩 (공공데이터포털 초당 호출 제한 대비) */
async function inBatches(ids, size, fn) {
  const out = [];
  for (let i = 0; i < ids.length; i += size) out.push(...(await Promise.all(ids.slice(i, i + size).map(fn))));
  return out;
}

const TTL_MS = 10 * 60000;
let cached = null; // { at, promise }

/** 홈 날씨 지도와 같은 모양: { base_time, regions[] } (10분 캐시) */
export function liveRegionalWeather() {
  if (cached && Date.now() - cached.at < TTL_MS) return cached.promise;
  const promise = load();
  promise.catch(() => (cached = null));
  cached = { at: Date.now(), promise };
  return promise;
}

async function load() {
  const ncst = ncstBase();
  const fcst = fcstBase();
  const [regions, warn] = await Promise.all([
    inBatches(Object.keys(GRID), 4, (id) => regionWeather(id, ncst, fcst)),
    warnings(),
  ]);
  const d = ncst.base_date;
  return {
    base_time: `${d.slice(0, 4)}-${d.slice(4, 6)}-${d.slice(6)}T${ncst.base_time.slice(0, 2)}:00:00+09:00`,
    regions: regions.map((r) => {
      const warning = warn[r.id] ?? null;
      return { ...r, warning, note: farmNote({ ...r, warning }) };
    }),
  };
}

// 지난 날씨(관측) 예시 데이터: 서버의 날씨 화면 파일에 연결되지 않았을 때만.
// 모양은 collector/weather_site 가 만드는 regions-daily.json · regions-monthly.json · meta.json 과 같다 (서버 수집기 v2 표 기준).
import { SIDO, addDays, seeded, todayIso } from "../utils/format";

// 시·도별 대략적인 기온 차이 (남쪽·바닷가는 따뜻하게, 강원은 서늘하게)
const OFFSET = { 서울: 0, 인천: -0.5, 경기: -1, 강원: -2.5, 충북: -0.5, 세종: 0, 대전: 0.5, 충남: 0, 전북: 0.5, 광주: 1.5, 전남: 2, 경북: 0, 대구: 1.5, 울산: 2, 부산: 3, 경남: 2, 제주: 4 };
// 1991~2020 평년 월 평균기온·강수량 (서울 대략값, 지역 차이는 OFFSET)
const NORMAL_TEMP = [-1.9, 0.7, 6.1, 12.6, 17.9, 22.2, 24.9, 25.7, 21.2, 14.8, 7.2, 0.4];
const NORMAL_RAIN = [16.8, 28.2, 36.9, 72.9, 103.6, 129.5, 414.4, 348.2, 141.5, 52.2, 51.1, 22.6];

const r1 = (n) => Math.round(n * 10) / 10;
const dayOfYear = (iso) => (new Date(`${iso}T00:00:00`) - new Date(`${iso.slice(0, 4)}-01-01T00:00:00`)) / 86400000;
// 평년 기온 곡선 (1월 중순 가장 춥고 8월 초 가장 더움)
const seasonal = (iso) => 12 - 14 * Math.cos((2 * Math.PI * (dayOfYear(iso) - 18)) / 365);

export function sampleWeatherHistory() {
  const last = addDays(todayIso(), -1);
  const generated = `${todayIso()}T06:00:00+09:00`;
  const daily = {};
  const monthly = {};
  const normals = {};
  for (const sido of SIDO) {
    const r = seeded(`weather-history|${sido}`);
    const off = OFFSET[sido];
    daily[sido] = Array.from({ length: 120 }, (_, i) => {
      const date = addDays(last, i - 119);
      const avg = seasonal(date) + off + (r() - 0.45) * 5;
      const rainy = r() < 0.22;
      const range = rainy ? 5 + r() * 3 : 8 + r() * 5;
      return {
        date,
        temp_avg: r1(avg),
        temp_max: r1(avg + range / 2),
        temp_min: r1(avg - range / 2),
        rain_mm: rainy ? r1(r() < 0.1 ? 60 + r() * 60 : 1 + r() * 25) : 0,
        humidity: r1(rainy ? 80 + r() * 15 : 50 + r() * 25),
        sun_hours: r1(rainy ? r() * 3 : 5 + r() * 5),
        gust: r1(5 + r() * 9),
        normal_temp: r1(seasonal(date) + off),
        normal_rain: r1(NORMAL_RAIN[Number(date.slice(5, 7)) - 1] / 30),
      };
    });
    normals[sido] = Object.fromEntries(NORMAL_TEMP.map((t, m) => [String(m + 1), { temp_avg: r1(t + off), rain_mm: r1(NORMAL_RAIN[m] * (0.8 + r() * 0.4)) }]));
    const [y, mo] = last.split("-").map(Number);
    monthly[sido] = Array.from({ length: 25 }, (_, i) => {
      const k = y * 12 + (mo - 2) - (24 - i); // 지난달까지 25개월
      const month = `${Math.floor(k / 12)}-${String((k % 12) + 1).padStart(2, "0")}`;
      const n = normals[sido][String((k % 12) + 1)];
      const temp = n.temp_avg + (r() - 0.35) * 2.4;
      return {
        month,
        temp_avg: r1(temp), temp_max: r1(temp + 5.5), temp_min: r1(temp - 5),
        rain_mm: r1(n.rain_mm * (0.4 + r() * 1.2)),
        hot_days: temp > 24 ? r1(r() * 8) : 0, frost_days: temp < 5 ? r1(10 + r() * 15) : 0,
        rain_days: r1(4 + r() * 8), windy_days: r1(r() * 2),
      };
    });
  }
  const lastMonth = monthly[SIDO[0]].at(-1).month;
  return {
    daily: { generated_at: generated, last_date: last, days: 120, regions: daily },
    monthly: { generated_at: generated, last_month: lastMonth, normal_period: "1991~2020", regions: monthly, normals },
    meta: {
      ok: true, error: null, generated_at: generated, checked_at: generated,
      source: { file: "날씨_대통합_일별.csv (예시)", modified_at: generated, size: 0 },
      format: "v2",
      ranges: { 시도_일: ["1991-01-01", last], 시군구_일: ["2015-01-01", last] },
      rows: {},
    },
    sample: true,
  };
}

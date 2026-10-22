// 관리자 데이터 수집 화면의 예시 데이터 (서버에 연결되지 않았을 때만). 모양은 collector/news 가 남기는 파일과 같다.
import { labelNews } from "./news";
import { seeded } from "../utils/format";

const REJECTED = [
  ["뜨끈한 시래기장어탕 단돈 1만원…장어돼지구이 맛집", -9, []],
  ["금리 고점은 늘 '부작용' 뒤에…금통위 동결", -4, []],
  ["\"행정 실수로 물거품 죄송\"…체전 출전 무산 사과", 0, []],
  ["'김도영 만루포' KIA, LG 13대 1 대파", -3, []],
  ["한국 자동차 부품사 성장…중국은 7배 빠른 질주", 0, []],
];

export function sampleNewsCollection(now = Date.now()) {
  const hour = 3600000;
  const last = Math.floor(now / hour) * hour + 2 * 60000; // 매시 2분쯤 수집했다고 가정
  const r = seeded("collect-log");
  const runs = Array.from({ length: 24 }, (_, i) => {
    const at = last - i * hour;
    const received = 180 + Math.round(r() * 160);
    const added = 10 + Math.round(r() * 30);
    const ok = i !== 9; // 예시: 9시간 전 한 번 실패
    return {
      started_at: new Date(at - 40000).toISOString(),
      finished_at: new Date(at).toISOString(),
      ok,
      queries: 27,
      calls: ok ? 27 + Math.round(r() * 4) : 1,
      received: ok ? received : 0,
      added: ok ? added : 0,
      rejected: ok ? received - added - Math.round(r() * 40) : 0,
      errors: ok ? [] : ["농산물 가격: HTTP 401: Authentication Failed (Invalid authentication information.)"],
      ...(ok && { stored_total: 5200 - i * 25, stored_recent: 640 - i * 3, oldest_at: new Date(now - 41 * 24 * hour).toISOString() }),
    };
  });
  const articles = labelNews(now);
  return {
    sample: true,
    log: { last_success_at: runs[0].started_at, interval_min: 60, runs },
    recent: { updated_at: runs[0].finished_at, count: articles.length, articles },
    rejected: {
      collected_at: runs[0].finished_at,
      articles: REJECTED.map(([title, score, items], i) => ({ title, summary: "", url: `https://example.com/rejected/${i}`, score, items, crops: [] })),
    },
  };
}

// 뉴스 필터 규칙을 실제 기사로 다듬기 위한 표본 저장 (테스트 모드 전용).
// npm run dev 를 테스트 모드(VITE_DATA_SOURCE=live)로 켜 둔 채, 다른 터미널의 frontend 폴더에서:
//   node scripts/news-sample.mjs
// → frontend/news-sample.json 에 검색어별 네이버 원본 응답을 저장한다 (키는 들어가지 않음, 커밋하지 않음)
import { writeFileSync } from "node:fs";
import { ITEMS } from "../src/mocks/catalog.js";

const BASE = process.env.DEV_URL ?? "http://localhost:5173";
const queries = ["농산물 가격", "농산물 수급", ...ITEMS.map((i) => i.name)];
const out = { saved_at: new Date().toISOString(), queries: {} };

for (const query of queries) {
  const q = new URLSearchParams({ query, display: 100, sort: "date" });
  const res = await fetch(`${BASE}/live/naver/search/v1/news?${q}`);
  const data = await res.json().catch(() => null);
  if (!res.ok || !Array.isArray(data?.items)) {
    console.error(`✗ ${query}: ${data?.error?.message ?? `HTTP ${res.status}`}`);
    process.exit(1);
  }
  out.queries[query] = data.items;
  console.log(`✓ ${query} ${data.items.length}건`);
}
writeFileSync("news-sample.json", JSON.stringify(out, null, 1));
console.log("저장: frontend/news-sample.json");

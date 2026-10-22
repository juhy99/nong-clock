// 글(검색어·뉴스 제목)에서 팜비드 품목 찾기. 통합 검색의 품목 판단과 뉴스 품목 태그가 같이 쓴다.
// 단어 목록은 shared/news_rules.json 에 있고, 뉴스 수집기(collector/news/rules.py)도 같은 파일·같은 방식으로 찾는다.
// 찾는 방식을 바꾸면 rules.py 도 똑같이 바꿔야 한다.
import RULES from "../../../shared/news_rules.json";

/** 품목 코드 → 이 이름이 나오면 그 품목으로 본다 (품목 이름 + 품종·별칭) */
export const ITEM_WORDS = RULES.items;

/** 품목 이름이 들어 있지만 품목 뜻이 아닌 말. 먼저 지우고 찾는다. */
const NOT_ITEM = RULES.not_item;

/** 글 전체에 이 말이 있으면 그 품목 이름은 다른 뜻으로 본다 (사과=謝過, 대파=경기 결과) */
const MISREAD = Object.fromEntries(Object.entries(RULES.misread).map(([code, re]) => [code, new RegExp(re)]));

/**
 * 팜비드 16개 품목 밖이지만 기사에 자주 나오는 작물. 뉴스 태그로만 보여 준다 (시세·예측 화면이 없으므로 링크 없음).
 * 품목이 늘어나면 규칙 파일에서 items 로 옮기면 된다.
 */
export const OTHER_CROPS = RULES.other_crops;

// 긴 이름부터 찾아야 "양배추" 안의 "배추", "배추" 안의 "배"를 잘못 세지 않는다
const byLength = (entries) => entries.flatMap(([code, words]) => words.map((w) => ({ code, w }))).sort((a, b) => b.w.length - a.w.length);
const WORDS = byLength(Object.entries(ITEM_WORDS));
const CROP_WORDS = byLength(Object.entries(OTHER_CROPS).map(([code, c]) => [code, c.words]));

const HANGUL = /[가-힣]/;
// 한 글자 품목(배, 무, 귤)은 "배송", "무료"처럼 다른 낱말의 일부인 경우가 많다.
// 앞에 한글이 없고, 뒤에 한글이 없거나 조사·"값" 같은 짧은 말이 올 때만 품목으로 본다.
const AFTER_SINGLE = RULES.single_char.after;

// "3배", "1.7배", "두 배", "몇 배"처럼 수를 세는 말 뒤의 한 글자는 품목이 아니다 (배수 표현)
const COUNT_BEFORE = new RegExp(RULES.single_char.count_before);

function okBoundary(text, start, w) {
  if (w.length > 1) return true;
  if (COUNT_BEFORE.test(text.slice(Math.max(0, start - 8), start))) return false;
  const before = text[start - 1];
  const after = text[start + 1];
  if (before && HANGUL.test(before)) return false;
  return !after || !HANGUL.test(after) || AFTER_SINGLE.includes(after);
}

/**
 * 글에 나온 품목 코드 (나온 순서대로, 중복 없이)
 * @param {string} text
 * @returns {string[]}
 */
export const findItems = (text) => matchCodes(text, WORDS).filter((code) => !MISREAD[code]?.test(String(text ?? "")));

/** 16개 품목 밖 작물 코드 (OTHER_CROPS 의 키, 예: "샤인머스캣 수출" → ["grape"]) */
export const findCrops = (text) => matchCodes(text, CROP_WORDS);

/** 검색어가 가리키는 품목 밖 작물 하나 (예: "샤인머스캣" → grape). 없으면 null */
export const cropOfQuery = (q) => findCrops(q)[0] ?? null;

function matchCodes(text, words) {
  let t = String(text ?? "");
  for (const n of NOT_ITEM) t = t.replaceAll(n, " ".repeat(n.length));
  const taken = new Array(t.length).fill(false);
  const hits = [];
  for (const { code, w } of words) {
    let i = t.indexOf(w);
    while (i !== -1) {
      const free = !taken.slice(i, i + w.length).some(Boolean);
      if (free && okBoundary(t, i, w)) {
        taken.fill(true, i, i + w.length);
        hits.push({ code, at: i });
      }
      i = t.indexOf(w, i + 1);
    }
  }
  return [...new Set(hits.sort((a, b) => a.at - b.at).map((h) => h.code))];
}

/** 검색어가 가리키는 품목 하나 (예: "사과", "부사 시세" → apple). 없으면 null */
export const itemOfQuery = (q) => findItems(q)[0] ?? null;

function distance(a, b) {
  const dp = Array.from({ length: a.length + 1 }, (_, i) => [i, ...new Array(b.length).fill(0)]);
  for (let j = 1; j <= b.length; j++) dp[0][j] = j;
  for (let i = 1; i <= a.length; i++)
    for (let j = 1; j <= b.length; j++)
      dp[i][j] = Math.min(dp[i - 1][j] + 1, dp[i][j - 1] + 1, dp[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
  return dp[a.length][b.length];
}

/** 오타 제안: "사괴" → "사과" (품목 이름과 한 글자만 다를 때) */
export function suggestItemName(q) {
  const word = q.trim();
  if (word.length < 2) return null;
  const hit = WORDS.find(({ w }) => w.length >= 2 && w.length === word.length && distance(w, word) === 1);
  return hit?.w ?? null;
}

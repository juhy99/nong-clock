// 글(검색어·뉴스 제목)에서 팜비드 품목 찾기. 통합 검색의 품목 판단과 뉴스 품목 태그가 같이 쓴다.
// 실제 서비스에서는 뉴스 태그를 서버가 기사를 저장할 때 붙인다(docs/06_api_spec.md 2-14). 규칙은 이 파일과 같게 옮기면 된다.

/** 품목 코드 → 이 이름이 나오면 그 품목으로 본다 (품목 이름 + 품종·별칭) */
export const ITEM_WORDS = {
  potato: ["감자", "햇감자"],
  onion: ["양파", "햇양파"],
  carrot: ["당근"],
  apple: ["사과", "부사", "홍로"],
  watermelon: ["수박"],
  napa_cabbage: ["배추", "월동배추", "고랭지배추", "절임배추", "김장배추"],
  radish: ["무", "월동무", "가을무"],
  tomato: ["토마토"],
  cabbage: ["양배추"],
  sweet_potato: ["고구마"],
  button_mushroom: ["양송이"],
  pear: ["배", "신고배"],
  king_oyster_mushroom: ["새송이"],
  green_onion: ["대파"],
  mandarin: ["감귤", "귤"],
  enoki_mushroom: ["팽이버섯", "팽이"],
};

/** 품목 이름이 들어 있지만 품목 뜻이 아닌 말. 먼저 지우고 찾는다. */
const NOT_ITEM = [
  "사과했", "사과하", "사과드", "사과를 요구", "부사장", "당근마켓", "당근과 채찍", "팽이치기",
  "배가 아프", "배 아프", "배가 고프", "배고프", "배를 채우", "배가 불러", "배부르",
  // 사과(謝過)·별명·비유
  "사과는커녕", "사과 요구", "사과를 촉구", "사과 촉구", "공식 사과", "대국민 사과", "사과의 뜻", "사과 한마디", "사과 없", "사과받", "사과문",
  "감자님", "고구마님", "고구마 전개", "고구마 같은", "고구마 답답",
  // 다른 작물 이름이 들어 있지만 작물이 아닌 말
  "고추장", "포도당", "포도막", "오이도",
];

/**
 * 팜비드 16개 품목 밖이지만 기사에 자주 나오는 작물. 뉴스 태그로만 보여 준다 (시세·예측 화면이 없으므로 링크 없음).
 * 품목이 늘어나면 여기서 ITEM_WORDS 로 옮기면 된다.
 */
export const OTHER_CROPS = {
  grape: { name: "포도", emoji: "🍇", words: ["포도", "샤인머스캣", "샤인머스켓", "캠벨얼리", "거봉", "청포도", "적포도"] },
  peach: { name: "복숭아", emoji: "🍑", words: ["복숭아"] },
  strawberry: { name: "딸기", emoji: "🍓", words: ["딸기", "설향"] },
  garlic: { name: "마늘", emoji: "🧄", words: ["마늘", "깐마늘"] },
  pepper: { name: "고추", emoji: "🌶️", words: ["고추", "건고추", "홍고추", "풋고추"] },
  paprika: { name: "파프리카", emoji: "🫑", words: ["파프리카"] },
  oriental_melon: { name: "참외", emoji: "🍈", words: ["참외"] },
  cucumber: { name: "오이", emoji: "🥒", words: ["오이"] },
  pumpkin: { name: "호박", emoji: "🎃", words: ["애호박", "단호박", "늙은호박"] },
};

// 긴 이름부터 찾아야 "양배추" 안의 "배추", "배추" 안의 "배"를 잘못 세지 않는다
const byLength = (entries) => entries.flatMap(([code, words]) => words.map((w) => ({ code, w }))).sort((a, b) => b.w.length - a.w.length);
const WORDS = byLength(Object.entries(ITEM_WORDS));
const CROP_WORDS = byLength(Object.entries(OTHER_CROPS).map(([code, c]) => [code, c.words]));

const HANGUL = /[가-힣]/;
// 한 글자 품목(배, 무, 귤)은 "배송", "무료"처럼 다른 낱말의 일부인 경우가 많다.
// 앞에 한글이 없고, 뒤에 한글이 없거나 조사·"값" 같은 짧은 말이 올 때만 품목으로 본다.
const AFTER_SINGLE = "값가는도를와과의은이랑·,";

// "3배", "1.7배", "두 배", "몇 배"처럼 수를 세는 말 뒤의 한 글자는 품목이 아니다 (배수 표현)
const COUNT_BEFORE = /([0-9.,]|(^|[^가-힣])(한|두|세|네|다섯|여섯|일곱|여덟|아홉|열|몇|수|수십|수백|수천|십|백|천|만|두세|서너|여러))\s*$/;

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
export const findItems = (text) => matchCodes(text, WORDS);

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

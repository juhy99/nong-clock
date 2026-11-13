import { averageText } from "../mocks/accuracy";
import { useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import { AUCTION_ENABLED } from "../features";
import { ITEMS50 } from "../mocks/items50";
import { MARKETS } from "../mocks/market";
import "./about.css";

/* 서비스 소개 (v17, 11-11): 유리 카드 머리 + 숫자 4칸 · 기능 칸 · 예측 흐름 1~4 · 가격 기준 · 자주 묻는 질문 · 만든 사람들 / 문의
   다른 화면이 거는 링크: #items #how #price #price-basis #grades #faq #faq-<질문> #team #contact
   #faq-price 처럼 질문 주소로 들어오면 그 질문을 펼쳐서 보여 줌 (홈 아래 "자주 묻는 질문" 칸) */
const N_ITEMS = ITEMS50.length;
const N_MARKETS = MARKETS.filter((m) => m.code !== "national").length;
const N_VARIETIES = ITEMS50.reduce((n, i) => n + (i.varieties?.length ?? 0), 0);
const STATS = [[N_MARKETS, "곳", "공영 도매시장"], [N_ITEMS, "품목", `예측 품목 · 품종 ${N_VARIETIES}가지`], [1, "년", "최대 예측 기간"], ["06:00", "", "매일 새 예측"]];

// ✏️ 팀 정보와 연락처는 여기만 고치면 된다.
const TEAM = [
  { name: "이름", role: "AI 가격 예측 · ML API(FastAPI)" },
  { name: "이름", role: "백엔드 · Spring Boot" },
  { name: "이름", role: "데이터 수집 · DB" },
  { name: "이름", role: "예측 모델링" },
];
const CONTACT = { email: "contact@nongclock.kr", phone: "02-000-0000", hours: "평일 10:00~18:00" };
const PROJECT = AUCTION_ENABLED ? "농산물 가격 예측·경매 플랫폼 팀 프로젝트 · 2026" : "농산물 가격 예측 플랫폼 팀 프로젝트 · 2026";

const FEATURES = [
  ["📈", "AI 가격 예측", `공영 도매시장 ${N_ITEMS}개 품목의 도매가(원/kg)를 도매시장 ${N_MARKETS}곳별로, 최대 1년 뒤 원하는 날짜까지 오차범위와 함께 매일 보여드려요.`, "/ai"],
  ["🌱", "작물 추천", "내 땅과 시작 날짜를 넣으면 수확기 예상 가격으로 마진이 높은 작물을, 작물을 고르면 가장 좋은 심는 날을 알려드려요.", "/recommend"],
  ...(AUCTION_ENABLED ? [["🔨", "농가 직거래 경매", "인증된 농가가 직접 경매를 열고, AI 참고가를 보며 시작가를 정할 수 있어요.", "/auctions"]] : []),
  ["⭐", "관심 품목", "관심 품목을 담아 두면 마이페이지에서 오늘 시세와 AI 1주 뒤 예측을 한눈에 볼 수 있어요.", "/mypage"],
];

// 가격 기준 안내 (/about#price-basis). 다른 화면에는 기준을 따로 적지 않고 여기에 모아 둔다.
const BASIS = [
  ["기본 기준 · 전국 상 등급", "고르는 칸이 없는 화면 (시세)", ["홈의 시세 띠 · 오늘의 주요 시세", "통합 검색의 품목 요약", "마이페이지 관심 품목 가격 변동", AUCTION_ENABLED ? "경매 등록의 AI 참고가 · 가격 알림" : "가격 알림"]],
  ["직접 고를 수 있어요", "시세·수급 화면", [`시장: 전국 평균 또는 ${N_MARKETS}개 도매시장`, "등급: 특 · 상 · 중 · 하 · 평균", "처음 열면 전국 · 상 등급이 선택돼 있어요", "통합 검색의 \"시장별 오늘 시세\"는 시장마다 보여 줘요"]],
  ["따로 정한 기준", "예측 · 소매가 · 품목", ["AI 예측은 공영도매시장 경매 단가(원/kg)예요 — 그날 총 경락 금액 ÷ 총 물량, 등급을 나누지 않은 농가 수취 경락가. AI 예측 화면은 고른 도매시장, 홈은 전국", "작물 추천은 토지가 있는 시·도 안 도매시장 가격으로 계산해요 (시장이 없는 세종·제주는 전국 평균, 운송비·유통 마진은 빼지 않아요)", "소매가는 전국 소매가 하나예요 (등급 구분 없음)", `예측 품목은 ${N_ITEMS}가지예요. 품종은 예측 화면에서 고를 수 있어요 (품목 예측에 품종별 가격 차이를 곱해 보여 줘요)`, "날짜 비교는 직전 거래일 대비예요"]],
];
const GRADE_ROWS = [
  ["특", "도매시장 경매에서 가장 좋은 품질로 매긴 등급", "시세·수급에서 골라 볼 수 있어요"],
  ["상", "거래가 꾸준한 좋은 품질 등급 · NongClock 시세의 기본 기준", "기본 시세 (AI 예측은 등급을 나누지 않은 경매 단가)"],
  ["중", "보통 품질 등급", "시세·수급에서 골라 볼 수 있어요"],
  ["하", "품질이 낮은 등급 · 거래가 없는 날이 많아요", "시세·수급에서 골라 볼 수 있어요"],
  ["평균", "모든 등급을 거래량만큼 반영한 가격", "시세·수급에서 골라 볼 수 있어요"],
];

const FLOW = [
  ["수집", "공영도매시장 경매 원장·가락시장·산지공판장 가격, 기상청 날씨, 정책 발표, 환율, 명절·공휴일 데이터를 모아요"],
  ["학습", `${N_ITEMS}품목 공영도매시장 경매 단가를 내일부터 1년 뒤까지 맞히는 모델을 학습하고, 지난 기간으로 오차(WAPE)를 검증해요`],
  ["예측", `품목·기간마다 검증 오차만큼 범위를 함께 보여 드려요 (품목 평균 ${averageText()}). 검증 성적이 기준선보다 나쁜 품목·기간은 참고용이에요`],
  ["활용", AUCTION_ENABLED ? "홈·AI 예측 화면과 경매 시작가 참고가에 바로 반영돼요" : "홈·AI 예측·작물 추천 화면에 바로 반영돼요"],
];

// 자주 묻는 질문 (11-13). [주소 id, 질문, 답]
const FAQ = [
  ["faq-price", "가격은 어떤 기준인가요?", <>따로 고르는 칸이 없는 화면의 가격은 모두 <b>전국 도매시장 · 상 등급 · 1kg</b> 기준이에요. AI 가격 예측은 등급을 나누지 않은 <b>경매 단가</b>(그날 총 경락 금액 ÷ 총 물량)예요. <a href="#price">가격 기준 자세히 ›</a></>],
  ["faq-grade", "특 · 상 · 중 · 하 등급은 무엇인가요?", <>도매시장 경매에서 품질에 따라 매기는 등급이에요. <b>상</b> 등급이 거래가 꾸준해서 기본 기준으로 써요. 시세 · 수급 화면에서 특 · 상 · 중 · 하 · 평균을 골라 볼 수 있어요. <a href="#grades">등급표 보기 ›</a></>],
  ["faq-range", "얼마나 먼 날까지 예측하나요?", <>내일부터 <b>1년 뒤</b>까지 원하는 날짜를 고를 수 있어요. 1주 · 1개월 · 6개월 · 1년 버튼으로 바로 고를 수도 있어요. 2개월까지는 주별로, 그보다 먼 날은 달별로 보여 드려요.</>],
  ["faq-accuracy", "예측은 얼마나 정확한가요?", <>지난 기간으로 검증한 오차를 품목 · 기간마다 함께 보여 드려요. 예측 화면의 "이 예측, 믿을 만한가요?"에서 신뢰도(100 − 오차)와 "실제 가격과 평균 ±n% 안에서 맞았어요"를 확인할 수 있어요. 품목 평균 오차는 {averageText()}예요. 오차가 큰 품목은 이름 옆에 <b>(!)</b>가 붙어요.</>],
  ["faq-update", "예측은 언제 새로 나오나요?", <>매일 <b>오전 6시</b>에 전날까지의 시세로 새 예측을 만들어요.</>],
  ["faq-source", "자료는 어디서 가져오나요?", <>도매가와 반입량은 <b>공영도매시장 경매 원장</b>, 소매가는 <b>KAMIS</b>(농산물유통정보), 날씨는 <b>기상청</b>, 농업 뉴스는 <b>네이버 뉴스 검색</b>에서 가져와요.</>],
  ["faq-margin", "작물 추천의 순수익은 어떻게 계산하나요?", <>달마다 예상 판매량 × AI 예상 가격에서 <b>농촌진흥청 평균 경영비와 임대료</b>를 뺀 값이에요. 운송비 · 유통 마진은 빼지 않아서 실제와 다를 수 있어요.</>],
  ["faq-member", "회원가입을 해야 쓸 수 있나요?", <>시세 · 수급, 농업 뉴스, 게시판 읽기는 누구나 볼 수 있어요. <b>AI 가격 예측 · 작물 추천 · 마이페이지</b>와 글쓰기는 로그인한 뒤에 쓸 수 있어요.</>],
];

export default function About() {
  // #faq-xxx 로 들어오면 그 질문을 펼치고 그 자리로 (머리말 높이만큼은 CSS scroll-margin)
  const { hash } = useLocation();
  useEffect(() => {
    if (!hash) return;
    const el = document.getElementById(decodeURIComponent(hash.slice(1)));
    if (!el) return;
    if (el.tagName === "DETAILS") el.open = true;
    requestAnimationFrame(() => el.scrollIntoView({ block: "start" }));
  }, [hash]);
  return (
    <div className="page ab">
      <section className="card ab-hero" id="items">
        <div>
          <div className="ab-eyebrow">농클락 NONGCLOCK</div>
          <h1>오늘 시세가 아니라,<br /><em>다음 주 가격</em>을 보고 거래하세요.</h1>
          <p>
            {AUCTION_ENABLED
              ? "NongClock은 AI 가격 예측과 온라인 경매를 하나로 묶은 농산물 거래 서비스예요. 날씨·명절·과거 시세를 학습한 모델이 앞으로의 도매가를 예측하고, 농가와 구매자는 그 예측을 참고해 경매로 직접 거래합니다."
              : "NongClock은 AI 가격 예측으로 농가의 판단을 돕는 서비스예요. 날씨·명절·과거 시세를 학습한 모델이 앞으로의 도매가를 예측하고, 그 예측으로 언제 무엇을 심으면 좋을지까지 알려드려요."}
          </p>
          <div className="ab-btns">
            <Link className="btn primary" to="/ai">AI 가격 예측 보기</Link>
            <Link className="btn" to={AUCTION_ENABLED ? "/auctions" : "/recommend"}>{AUCTION_ENABLED ? "경매 마켓 둘러보기" : "작물 추천 받기"}</Link>
          </div>
        </div>
        <div className="ab-stats">
          {STATS.map(([v, u, l]) => (
            <div key={l}><b>{v}<small>{u}</small></b><span>{l}</span></div>
          ))}
        </div>
      </section>

      <div className="ab-feats">
        {FEATURES.map(([icon, title, desc, to]) => (
          <Link key={title} to={to} className="card ab-feat">
            <i aria-hidden>{icon}</i>
            <h3>{title}</h3>
            <p>{desc}</p>
          </Link>
        ))}
      </div>

      <section className="card" id="how">
        <h2 className="ab-h">이렇게 예측해요</h2>
        <ol className="ab-flow">
          {FLOW.map(([step, desc], i) => (
            <li key={step}><em aria-hidden>{i + 1}</em><b>{step}</b><p>{desc}</p></li>
          ))}
        </ol>
        <p className="ab-note">예측은 참고용 정보예요. 실제 가격은 수급·유통 상황에 따라 달라질 수 있어요.</p>
      </section>

      <section className="card" id="price">
        <span id="price-basis" />
        <h2 className="ab-h">가격은 이렇게 보여드려요</h2>
        <div className="basis-lead">
          <div className="big">따로 고르지 않는 곳의 가격은 모두<br /><em>전국 도매시장 · 상 등급 · 1kg</em> 기준이에요</div>
          <div className="basis-chips"><span>전국 도매시장 평균</span><span>상 등급</span><span>원/kg</span></div>
        </div>
        <div className="basis-grid">
          {BASIS.map(([tag, title, lines], i) => (
            <div key={tag}>
              <span className={`basis-tag t${i}`}>{tag}</span>
              <h3>{title}</h3>
              <ul>{lines.map((l) => <li key={l}>{l}</li>)}</ul>
            </div>
          ))}
        </div>
        <div className="table-wrap" id="grades">
          <table className="table grade-table">
            <thead><tr><th>등급</th><th>뜻</th><th>어디에 쓰나요</th></tr></thead>
            <tbody>
              {GRADE_ROWS.map(([g, desc, use]) => (
                <tr key={g} className={g === "상" ? "main" : ""}>
                  <td><span className="g">{g}</span></td>
                  <td>{desc}</td>
                  <td>{use}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="ab-note">시세·수급 화면에서 다른 시장이나 등급을 고르면, 홈이나 예측 화면의 가격과 숫자가 다를 수 있어요. 기준이 달라서 생기는 차이예요.</p>
      </section>

      <section className="card" id="faq">
        <h2 className="ab-h">자주 묻는 질문</h2>
        <div className="ab-faq">
          {FAQ.map(([id, q, a]) => (
            <details key={id} id={id}>
              <summary>{q}</summary>
              <p>{a}</p>
            </details>
          ))}
        </div>
      </section>

      <div className="ab-two">
        <section className="card" id="team">
          <div className="ab-hrow"><h2 className="ab-h">만든 사람들</h2><small>{PROJECT}</small></div>
          <div className="ab-team">
            {TEAM.map((m, i) => (
              <div key={i}><i aria-hidden>👤</i><span><b>{m.name}</b><small>{m.role}</small></span></div>
            ))}
          </div>
        </section>
        <section className="card" id="contact">
          <h2 className="ab-h">문의하기</h2>
          <dl className="ab-contact">
            <div><dt>이메일</dt><dd><a href={`mailto:${CONTACT.email}`}>{CONTACT.email}</a></dd></div>
            <div><dt>전화</dt><dd>{CONTACT.phone} <small>{CONTACT.hours}</small></dd></div>
          </dl>
          <p className="ab-note">서비스 이용, 데이터 오류 제보, 제휴 문의 모두 환영해요.{AUCTION_ENABLED && " 경매 관련 신고는 각 경매 화면의 🚨 신고 버튼을 이용해 주세요."}</p>
        </section>
      </div>
    </div>
  );
}

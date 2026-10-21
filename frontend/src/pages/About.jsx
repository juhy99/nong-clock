import { Link } from "react-router-dom";

// ✏️ 팀 정보와 연락처는 여기만 고치면 된다.
const TEAM = [
  { name: "이름", role: "AI 가격 예측 · ML API(FastAPI)" },
  { name: "이름", role: "백엔드 · Spring Boot" },
  { name: "이름", role: "데이터 수집 · DB" },
  { name: "이름", role: "예측 모델링" },
];
const CONTACT = { email: "contact@farmbid.kr", phone: "02-000-0000", hours: "평일 10:00~18:00" };
const PROJECT = "농산물 가격 예측·경매 플랫폼 팀 프로젝트 · 2026";

const FEATURES = [
  ["🤖", "AI 가격 예측", "주요 16개 품목의 전국 도매가(원/kg)를 최대 30일 뒤 원하는 날짜까지 오차범위와 함께 매일 보여드려요.", "/ai"],
  ["🌧️", "이상기후 주의 구간", "폭우·한파처럼 예측이 흔들릴 수 있는 기간을 미리 표시하고, 그때 모델 오차가 얼마나 커졌는지도 알려드려요.", "/ai"],
  ["🔨", "농가 직거래 경매", "인증된 농가가 직접 경매를 열고, AI 참고가를 보며 시작가를 정할 수 있어요.", "/auctions"],
  ["🔔", "관심 품목 알림", "관심 품목의 시세 변동과 이상기후 소식, 입찰 결과를 알림으로 받아보세요.", "/mypage"],
];

// 가격 기준 안내 (/about#price-basis). 다른 화면에는 기준을 따로 적지 않고 여기에 모아 둔다.
const BASIS = [
  ["기본 기준 · 전국 상 등급", "고르는 칸이 없는 화면", ["홈의 시세 띠 · 오늘의 주요 시세", "홈과 AI 예측 화면의 예측 가격", "통합 검색의 품목 요약", "마이페이지 관심 품목 가격 변동", "경매 등록의 AI 참고가 · 가격 알림"]],
  ["직접 고를 수 있어요", "시세·수급 화면", ["시장: 전국 평균 또는 32개 도매시장", "등급: 특 · 상 · 중 · 하 · 평균", "처음 열면 전국 · 상 등급이 선택돼 있어요", "통합 검색의 \"시장별 오늘 시세\"는 시장마다 보여 줘요"]],
  ["따로 정한 기준", "예측 · 소매가 · 품목", ["AI 예측은 전국 · 상 등급 하나만 해요", "소매가는 전국 소매가 하나예요 (등급 구분 없음)", "품목은 16가지이고 품종은 나누지 않아요 (예: 무 = 가을무·고랭지무 모두)", "날짜 비교는 직전 거래일 대비예요"]],
];
const GRADE_ROWS = [
  ["특", "도매시장 경매에서 가장 좋은 품질로 매긴 등급", "시세·수급에서 골라 볼 수 있어요"],
  ["상", "거래가 꾸준한 좋은 품질 등급 · 팜비드의 기본 기준", "기본 가격 · AI 예측"],
  ["중", "보통 품질 등급", "시세·수급에서 골라 볼 수 있어요"],
  ["하", "품질이 낮은 등급 · 거래가 없는 날이 많아요", "시세·수급에서 골라 볼 수 있어요"],
  ["평균", "모든 등급을 거래량만큼 반영한 가격", "시세·수급에서 골라 볼 수 있어요"],
];

const FLOW = [
  ["① 수집", "KAMIS 도매가격, 기상청 날씨, 명절·공휴일 데이터를 모아요"],
  ["② 학습", "품목별 가격 예측 모델을 학습하고, 과거 기간으로 오차를 검증해요"],
  ["③ 예측", "매일 앞으로 30일 동안의 가격과 신뢰도를 계산해요"],
  ["④ 활용", "홈·AI 예측 화면과 경매 시작가 참고가에 바로 반영돼요"],
];

export default function About() {
  return (
    <div className="page">
      <section className="about-hero">
        <div style={{ opacity: 0.8, fontWeight: 600 }}>팜비드 FarmBid</div>
        <h1>
          오늘 시세가 아니라,
          <br />
          다음 주 가격을 보고 거래하세요.
        </h1>
        <p>
          팜비드는 AI 가격 예측과 온라인 경매를 하나로 묶은 농산물 거래 서비스예요. 날씨·명절·과거 시세를 학습한 모델이
          앞으로의 도매가를 예측하고, 농가와 구매자는 그 예측을 참고해 경매로 직접 거래합니다.
        </p>
        <div style={{ display: "flex", gap: 8, marginTop: 22, flexWrap: "wrap" }}>
          <Link className="btn" style={{ border: "none", color: "var(--green-dark)" }} to="/ai">AI 가격예측 보기</Link>
          <Link className="btn" style={{ background: "rgba(255,255,255,.15)", borderColor: "transparent", color: "#fff" }} to="/auctions">경매 마켓 둘러보기</Link>
        </div>
      </section>

      <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(230px, 1fr))" }}>
        {FEATURES.map(([icon, title, desc, to]) => (
          <Link key={title} to={to} className="card feature">
            <div className="ic">{icon}</div>
            <h3>{title}</h3>
            <p className="muted small">{desc}</p>
          </Link>
        ))}
      </div>

      <section className="card">
        <h2 style={{ marginBottom: 14 }}>이렇게 예측해요</h2>
        <div className="flow">
          {FLOW.map(([step, desc]) => (
            <div key={step}>
              <b>{step}</b>
              <p className="small muted" style={{ margin: "4px 0 0" }}>{desc}</p>
            </div>
          ))}
        </div>
        <p className="hint" style={{ marginBottom: 0 }}>
          예측은 참고용 정보예요. 실제 가격은 수급·유통 상황에 따라 달라질 수 있어요.
        </p>
      </section>

      <section className="card" id="price-basis">
        <h2 style={{ marginBottom: 12 }}>가격은 이렇게 보여드려요</h2>
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
        <div className="table-wrap">
          <table className="table grade-table">
            <thead><tr><th>등급</th><th>뜻</th><th>어디에 쓰나요</th></tr></thead>
            <tbody>
              {GRADE_ROWS.map(([g, desc, use]) => (
                <tr key={g} className={g === "상" ? "main" : ""}>
                  <td><span className="g">{g}</span></td>
                  <td>{desc}</td>
                  <td className={g === "상" ? "" : "muted"}>{use}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="hint" style={{ marginBottom: 0 }}>
          시세·수급 화면에서 다른 시장이나 등급을 고르면, 홈이나 예측 화면의 가격과 숫자가 다를 수 있어요. 기준이 달라서 생기는 차이예요.
        </p>
      </section>

      <div className="two-col">
        <section className="card">
          <h2 style={{ marginBottom: 12 }}>만든 사람들</h2>
          <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 8 }}>
            {TEAM.map((m, i) => (
              <div key={i} className="member">
                <div className="avatar">👤</div>
                <div>
                  <b>{m.name}</b>
                  <div className="muted small">{m.role}</div>
                </div>
              </div>
            ))}
          </div>
          <p className="muted small" style={{ marginBottom: 0 }}>{PROJECT}</p>
        </section>
        <section className="card" style={{ display: "grid", gap: 10, alignContent: "start" }}>
          <h2>문의하기</h2>
          <div>✉️ 이메일 <a className="link" href={`mailto:${CONTACT.email}`}>{CONTACT.email}</a></div>
          <div>📞 전화 <b>{CONTACT.phone}</b> <span className="muted small">({CONTACT.hours})</span></div>
          <p className="muted small" style={{ margin: 0 }}>
            서비스 이용, 데이터 오류 제보, 제휴 문의 모두 환영해요. 경매 관련 신고는 각 경매 화면의 🚨 신고 버튼을 이용해 주세요.
          </p>
        </section>
      </div>
    </div>
  );
}

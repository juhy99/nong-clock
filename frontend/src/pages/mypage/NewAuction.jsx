import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { AUCTION_DAYS, createAuction } from "../../api/auction";
import { getItems, predict } from "../../api/ml";
import { useAuth } from "../../components/AuthContext";
import { Async, useAsync } from "../../components/common";
import { won } from "../../utils/format";

const OTHER = "__other";

function validate(f) {
  const e = {};
  if (!f.item) e.item = "품목을 고르세요";
  if (f.title.trim().length < 5) e.title = "상품명을 5자 이상 입력하세요";
  if (!f.origin.trim()) e.origin = "산지를 입력하세요";
  if (!(Number(f.weight_kg) > 0)) e.weight_kg = "총 중량(kg)을 입력하세요";
  if (!(Number(f.start_price) >= 1000)) e.start_price = "시작가는 1,000원 이상이어야 합니다";
  if (f.description.trim().length < 10) e.description = "상품 설명을 10자 이상 입력하세요";
  return e;
}

/** AI 1주 예측가 × 총 중량 → 시작가를 정할 때 참고 */
function AiHint({ item, weight }) {
  const state = useAsync(() => (item && item !== OTHER ? predict({ item, horizon: 7 }) : Promise.resolve(null)), [item]);
  const p = state.data;
  if (!p) return <span className="hint">16개 예측 품목이면 AI 참고가를 보여드려요</span>;
  const kg = Number(weight) || 0;
  return (
    <span className="hint ok">
      💡 AI 참고가: 1주 후 예상 도매가 {won(p.predicted_price)}원/kg
      {kg > 0 && ` → ${kg}kg 약 ${won(p.predicted_price * kg)}원`}
    </span>
  );
}

export default function NewAuction() {
  const { user } = useAuth();
  const nav = useNavigate();
  const items = useAsync(getItems);
  const [f, setF] = useState({ item: "", title: "", origin: user.region ?? "", weight_kg: "", start_price: "", days: 3, description: "" });
  const [touched, setTouched] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const errors = validate(f);
  const err = (k) => touched && errors[k] && <span className="hint error">{errors[k]}</span>;

  if (user.type !== "seller")
    return (
      <div className="page">
        <div className="card state">판매자(농가) 회원만 경매를 등록할 수 있습니다.</div>
      </div>
    );

  async function submit(e, list) {
    e.preventDefault();
    setTouched(true);
    if (Object.keys(errors).length) return;
    const info = list.find((i) => i.code === f.item);
    setBusy(true);
    try {
      await createAuction(user, {
        item: info ? info.code : null,
        emoji: info?.emoji ?? "🧺",
        title: f.title,
        origin: f.origin,
        weight_kg: Number(f.weight_kg),
        start_price: Number(f.start_price),
        days: Number(f.days),
        description: f.description,
      });
      nav("/mypage?tab=auctions", { replace: true });
    } catch (e2) {
      setError(e2.message);
      setBusy(false);
    }
  }

  return (
    <div className="page" style={{ maxWidth: 820 }}>
      <div className="page-head">
        <Link className="link" to="/mypage?tab=auctions">← 내 경매</Link>
        <h1 style={{ marginTop: 6 }}>새 경매 등록</h1>
        <p>관리자 승인 후 경매 마켓에 노출됩니다</p>
      </div>
      <Async state={items}>
        {(list) => (
          <form className="card" style={{ display: "grid", gap: 16 }} onSubmit={(e) => submit(e, list)} noValidate>
            <div className="two-col">
              <div className="field">
                <label htmlFor="item">품목</label>
                <select id="item" className="input" value={f.item} onChange={set("item")}>
                  <option value="">선택하세요</option>
                  {list.map((i) => <option key={i.code} value={i.code}>{i.emoji} {i.name}</option>)}
                  <option value={OTHER}>🧺 기타 (예측 품목 외)</option>
                </select>
                {err("item")}
              </div>
              <div className="field">
                <label htmlFor="origin">산지</label>
                <input id="origin" className="input" value={f.origin} onChange={set("origin")} placeholder="예: 충남 논산" />
                {err("origin")}
              </div>
            </div>
            <div className="field">
              <label htmlFor="title">상품명</label>
              <input id="title" className="input" value={f.title} onChange={set("title")} placeholder="예: 논산 설향 딸기 2kg × 5박스" />
              {err("title")}
            </div>
            <div className="two-col">
              <div className="field">
                <label htmlFor="weight">총 중량 (kg)</label>
                <input id="weight" className="input" type="number" min="0" step="0.1" value={f.weight_kg} onChange={set("weight_kg")} />
                {err("weight_kg")}
              </div>
              <div className="field">
                <label htmlFor="days">경매 기간</label>
                <select id="days" className="input" value={f.days} onChange={set("days")}>
                  {AUCTION_DAYS.map((d) => <option key={d} value={d}>{d}일</option>)}
                </select>
              </div>
            </div>
            <div className="field">
              <label htmlFor="price">시작가 (원)</label>
              <input id="price" className="input" type="number" min="1000" step="1000" value={f.start_price} onChange={set("start_price")} />
              <AiHint item={f.item} weight={f.weight_kg} />
              {err("start_price")}
            </div>
            <div className="field">
              <label>상품 사진</label>
              <div className="input muted small" style={{ height: 80, display: "grid", placeItems: "center", background: "#f8f8f4" }}>
                📷 사진 올리기는 Spring 서버 연결 후 제공됩니다
              </div>
            </div>
            <div className="field">
              <label htmlFor="desc">상품 설명</label>
              <textarea id="desc" className="input" rows={4} value={f.description} onChange={set("description")} placeholder="수확일, 보관·배송 방법, 상품 상태 등" />
              {err("description")}
            </div>
            {error && <p className="hint error">{error}</p>}
            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
              <Link className="btn" to="/mypage?tab=auctions">취소</Link>
              <button className="btn primary" disabled={busy}>경매 등록하기</button>
            </div>
          </form>
        )}
      </Async>
    </div>
  );
}

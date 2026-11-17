import { useEffect, useRef, useState } from "react";
import { predict } from "../../api/ml";
import { getTodayPrices } from "../../api/market";
import { useAuth } from "../../components/AuthContext";
import { Async, PctChange, PriceChange, SectionHead, useAsync } from "../../components/common";
import { md, wonPerKg } from "../../utils/format";
import ItemImage from "../../components/ItemImage";
import { CATEGORIES50, ITEMS50, itemOf } from "../../mocks/items50";

/** 관심 품목의 오늘 시세 변동 + AI 1주 예측 (마이페이지 상단) */
export default function FavoriteAlerts({ onEdit }) {
  const { user } = useAuth();
  const favorites = user.favorites ?? [];
  const state = useAsync(async () => {
    if (!favorites.length) return [];
    const today = await getTodayPrices();
    const rows = today.items.filter((p) => favorites.includes(p.item));
    // 예측 없는 품목(출하철 밖 등, DB 예측기 404)은 그 품목만 '예측 없음' (11-11)
    const preds = await Promise.all(rows.map((p) => predict({ item: p.item, horizon: 7 }).catch((e) => ({ season: e.detail?.season ?? null }))));
    return rows.map((p, i) => ({ ...p, compared_date: today.compared_date, forecast_pct: preds[i]?.change_pct ?? null, season: preds[i]?.season ?? null }));
  }, [favorites.join()]);

  return (
    <section className="card">
      <SectionHead
        title="🔔 관심 품목 가격 변동"
        desc="오늘 도매가(직전 조사일 대비)와 AI 1주 예측"
        right={<button className="link" onClick={onEdit}>관심 품목 편집</button>}
      />
      <Async state={state} empty="관심 품목을 고르면 여기에서 시세와 예측을 한눈에 볼 수 있어요">
        {(rows) => (
          <div style={{ display: "grid", gap: 8 }}>
            {rows.map((p) => (
              <div key={p.item} className="alert-row">
                <ItemImage code={p.item} emoji={p.emoji} alt="" className="sm" />
                <b>{p.name}</b>
                <span className="num">{wonPerKg(p.price)}</span>
                <PriceChange change={p.change} changePct={p.change_pct} comparedDate={p.compared_date} className="small" />
                <span className="ai small muted">
                  AI 예측: 1주 후 {p.forecast_pct != null ? <><PctChange value={p.forecast_pct} /> (최근 7일 평균 대비)</> : p.season?.label ? (p.season.next_start ? `${md(p.season.next_start)}부터 예측 (주로 ${p.season.label})` : `출하철 아님 (주로 ${p.season.label})`) : "예측 없음"}
                </span>
              </div>
            ))}
          </div>
        )}
      </Async>
    </section>
  );
}

/* 관심 품목 고르기 화면 (11-16): 50개를 한 번에 늘어놓지 않고
   위에 "고른 품목"(× 로 빼기) · 이름/초성 검색 · 부류 탭 → 그 부류 품목만 칸으로 보여 줌. 품목 목록은 shared/items50.json (서버 없이도 뜸) */
const CHO = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ";
const choOf = (s) => [...s].map((ch) => { const c = ch.charCodeAt(0) - 0xac00; return c >= 0 && c < 11172 ? CHO[Math.floor(c / 588)] : ch; }).join("");
const matches = (name, q) => name.includes(q) || choOf(name).includes(q);

/** 관심 품목 고르기 탭.
 * 11-16: 빠르게 연달아 누르면 하나가 빠지던 문제 — 예전엔 서버 응답(로그인 정보)이 오기 전의 목록으로 다음 저장을 만들어
 * 마지막 저장이 앞의 것을 덮었다. 이제 화면 목록을 바로 바꾸고(latest), 저장은 한 번에 하나씩 차례로 '가장 최근 목록'을 보낸다 */
export function FavoritePicker() {
  const { user, updateProfile } = useAuth();
  const saved = user.favorites ?? [];
  const [picked, setPicked] = useState(saved);
  const [err, setErr] = useState("");
  const latest = useRef(saved);
  const pending = useRef(0);
  // 처음 탭: 첫 관심 품목의 부류 (없으면 첫 부류). "전체"는 맨 끝에 둬서 50개가 한꺼번에 뜨지 않게
  const [cat, setCat] = useState(() => itemOf(saved[0])?.category ?? CATEGORIES50[0]);
  const [q, setQ] = useState("");
  const chain = useRef(Promise.resolve());
  // 다른 곳(로그인·새로 고침)에서 목록이 바뀌면 따라감 — 저장 중에는 화면 목록이 더 최신이라 그대로 둠
  useEffect(() => {
    if (pending.current === 0) {
      latest.current = saved;
      setPicked(saved);
    }
  }, [saved.join()]);
  const toggle = (code) => {
    const cur = latest.current;
    const next = cur.includes(code) ? cur.filter((c) => c !== code) : [...cur, code];
    latest.current = next;
    setPicked(next);
    setErr("");
    pending.current += 1;
    chain.current = chain.current
      .then(() => (latest.current === next ? updateProfile({ favorites: next }) : null)) // 더 새 목록이 있으면 그 저장에 맡김
      .catch((e) => setErr(e.message || "관심 품목을 저장하지 못했습니다"))
      .finally(() => {
        pending.current -= 1;
      });
  };
  const query = q.replace(/\s/g, "");
  const shown = query ? ITEMS50.filter((i) => matches(i.name, query)) : ITEMS50.filter((i) => cat === "전체" || i.category === cat);
  const chosen = picked.map(itemOf).filter(Boolean);
  return (
    <section className="card mp-fav">
      <SectionHead title="관심 품목" desc="고른 품목은 마이페이지 위 '관심 품목 가격'에 보여요" />
      {err && <p className="error small" role="alert">{err}</p>}
      <div className="mp-fav-picked">
        <span className="lbl">고른 품목 <b>{chosen.length}</b></span>
        {chosen.length ? chosen.map((i) => (
          <button key={i.code} type="button" className="chip" onClick={() => toggle(i.code)} aria-label={`${i.name} 빼기`}>
            <ItemImage code={i.code} emoji={i.emoji} alt="" className="xs" /> {i.name} <span aria-hidden>×</span>
          </button>
        )) : <span className="none">아래에서 품목을 눌러 담아 보세요</span>}
      </div>
      <div className="mp-fav-bar">
        <input className="input" type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="🔍 품목 이름 또는 초성 (예: ㅇㅍ)" aria-label="품목 검색" />
        <div className="mp-fav-cats" role="tablist">
          {[...CATEGORIES50, "전체"].map((c) => (
            <button key={c} type="button" role="tab" aria-selected={!query && cat === c} className={!query && cat === c ? "on" : ""} onClick={() => { setCat(c); setQ(""); }}>
              {c}<em>{c === "전체" ? ITEMS50.length : ITEMS50.filter((i) => i.category === c).length}</em>
            </button>
          ))}
        </div>
      </div>
      {query && <p className="mp-fav-res">'{q.trim()}' 검색 결과 {shown.length}개</p>}
      {shown.length ? (
        <div className="mp-fav-grid">
          {shown.map((i) => {
            const on = picked.includes(i.code);
            return (
              <button key={i.code} type="button" className={on ? "on" : ""} aria-pressed={on} onClick={() => toggle(i.code)}>
                <ItemImage code={i.code} emoji={i.emoji} alt="" className="sm" />
                <span>{i.name}</span>
                <i aria-hidden>{on ? "✓" : "+"}</i>
              </button>
            );
          })}
        </div>
      ) : <p className="mp-fav-res">찾는 품목이 없어요. 예측 품목 50개 안에서만 고를 수 있어요.</p>}
    </section>
  );
}

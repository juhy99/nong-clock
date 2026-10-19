import { getItems, predict } from "../../api/ml";
import { getTodayPrices } from "../../api/market";
import { useAuth } from "../../components/AuthContext";
import { Async, PctChange, PriceChange, SectionHead, useAsync } from "../../components/common";
import { wonPerKg } from "../../utils/format";
import ItemImage from "../../components/ItemImage";

/** 관심 품목의 오늘 시세 변동 + AI 1주 예측 (마이페이지 상단) */
export default function FavoriteAlerts({ onEdit }) {
  const { user } = useAuth();
  const favorites = user.favorites ?? [];
  const state = useAsync(async () => {
    if (!favorites.length) return [];
    const today = await getTodayPrices();
    const rows = today.items.filter((p) => favorites.includes(p.item));
    const preds = await Promise.all(rows.map((p) => predict({ item: p.item, horizon: 7 })));
    return rows.map((p, i) => ({ ...p, compared_date: today.compared_date, forecast_pct: preds[i].change_pct }));
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
                  AI 예측: 1주 후 <PctChange value={p.forecast_pct} />
                </span>
              </div>
            ))}
          </div>
        )}
      </Async>
    </section>
  );
}

/** 관심 품목 고르기 탭 */
export function FavoritePicker() {
  const { user, updateProfile } = useAuth();
  const items = useAsync(getItems);
  const favorites = user.favorites ?? [];
  const toggle = (code) =>
    updateProfile({ favorites: favorites.includes(code) ? favorites.filter((c) => c !== code) : [...favorites, code] });
  return (
    <section className="card">
      <SectionHead title="관심 품목" desc="탭해서 추가·해제 · 고른 품목은 위 가격 변동과 알림에 쓰여요" />
      <Async state={items}>
        {(rows) => (
          <div className="pills">
            {rows.map((i) => (
              <button key={i.code} className={`pill ${favorites.includes(i.code) ? "on" : ""}`} onClick={() => toggle(i.code)}>
                <ItemImage code={i.code} emoji={i.emoji} alt="" className="xs" /> {i.name}
              </button>
            ))}
          </div>
        )}
      </Async>
    </section>
  );
}

import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { getMyActivity } from "../../api/board";
import { getPriceHistory, getTodayPrices } from "../../api/market";
import { predict } from "../../api/ml";
import { getNotifications, markRead, onNotificationsChanged } from "../../api/notify";
import { USER_TYPE_LABEL, canSell, useAuth } from "../../components/AuthContext";
import { useAsync } from "../../components/common";
import { NOTIFY_TYPES } from "../../mocks/notifications";
import { AUCTION_ENABLED, NOTIFY_ENABLED } from "../../features";
import { boardDate, md, timeAgo, won } from "../../utils/format";
import { FavoritePicker } from "./Favorites";
import MyAuctions from "./MyAuctions";
import MyBids from "./MyBids";
import Profile from "./Profile";
import "./mypage.css";

/* ─────────────────────────────────────────────
   마이페이지 (v17, 11-11)
   위: 내 정보 + 숫자 4칸(관심 품목 · 새 알림 · 내가 쓴 글 · 내가 쓴 댓글) — 알림을 끄면(features.js) 새 알림 · 알림 목록 · 알림 설정은 숨김
   왼쪽: 관심 품목 가격(오늘 도매가 · 8거래일 흐름 · AI 1주 뒤) · 내가 쓴 글/댓글
   오른쪽: 알림 · 내 정보·알림 설정 요약
   "내 정보 수정" · "관심 품목 더하기" 는 같은 화면 안에서 편집 화면으로 바뀜 (?tab=profile · ?tab=watch)
   신고 내역은 신고 기능을 뺐으므로 없음
   ───────────────────────────────────────────── */

/** 작은 흐름 그래프 (빨강 = 오름, 파랑 = 내림) */
function Spark({ values }) {
  if (values.length < 2) return <svg className="mp-spark" />;
  const W = 200, H = 44, lo = Math.min(...values), hi = Math.max(...values);
  const X = (i) => (i * W) / (values.length - 1), Y = (v) => 4 + (1 - (v - lo) / (hi - lo || 1)) * (H - 8);
  const up = values.at(-1) >= values[0];
  const c = up ? "#d92d20" : "#1d5fd8";
  const pl = values.map((v, i) => `${X(i)},${Y(v)}`).join(" ");
  return (
    <svg className="mp-spark" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" aria-hidden>
      <polygon points={`0,${H} ${pl} ${W},${H}`} fill={up ? "rgba(217,45,32,.08)" : "rgba(29,95,216,.08)"} />
      <polyline points={pl} fill="none" stroke={c} strokeWidth="2" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

const FAV_SHOW = 7;   // 카드 7개 + '바꾸기' 1칸 = 두 줄
const mdOf = (iso) => `${Number(iso.slice(5, 7))}/${Number(iso.slice(8, 10))}`;

function FavCards({ onAdd }) {
  const { user } = useAuth();
  const favorites = user.favorites ?? [];
  const state = useAsync(async () => {
    if (!favorites.length) return [];
    const today = await getTodayPrices();
    // 11-17: 3개만 자르던 것 → 고른 순서대로 FAV_SHOW 개까지 (넘으면 '외 N개'), 관심 품목 4개인데 3개만 보이던 문제
    const rows = favorites.map((f) => today.items.find((p) => p.item === f)).filter(Boolean).slice(0, FAV_SHOW);
    return Promise.all(rows.map(async (p) => {
      const [hist, pred] = await Promise.all([getPriceHistory(p.item, { days: 8 }).catch(() => null), predict({ item: p.item, horizon: 7 }).catch((e) => ({ season: e.detail?.season ?? null }))]);
      return { ...p, compared_date: today.compared_date, spark: (hist?.points ?? []).map((x) => x.price).filter((v) => v != null), pred: pred?.season !== undefined ? null : pred, season: pred?.season ?? null };
    }));
  }, [favorites.join()]);
  return (
    <div className="mp-favs">
      {(state.data ?? []).map((p) => {
        const up = (p.change ?? 0) >= 0;
        return (
          <Link key={p.item} className="mp-fav" to={`/search?q=${encodeURIComponent(p.name)}`}>
            <div className="nm"><span aria-hidden>{p.emoji}</span>{p.name}</div>
            {/* 11-17: 오늘 거래가 없으면 '-원 ▲0원 (0.0%)' 대신 거래 없음 + 마지막 거래일 */}
            {p.price != null ? (
              <>
                <div className="p">{won(p.price)}원<small>/kg</small></div>
                {p.change != null
                  ? <div className="d"><b className={up ? "up" : "down"}>{up ? "▲" : "▼"} {won(Math.abs(p.change))}원 ({Math.abs(p.change_pct ?? 0).toFixed(1)}%)</b><br />직전 거래일 대비</div>
                  : <div className="d">직전 거래일 값이 없어 비교 안 함</div>}
              </>
            ) : (
              <>
                <div className="p none">오늘 거래 없음</div>
                <div className="d">{p.pred?.base_price_date ? `마지막 거래 ${mdOf(p.pred.base_price_date)} · 그때 7일 평균 ${won(p.pred.base_price)}원/kg` : "최근 거래가 없어요"}</div>
              </>
            )}
            <Spark values={p.spark} />
            {p.pred && (p.pred.base_stale ? (
              /* 11-17: 마지막 거래가 오래전이면 변동률(%)을 보여 주지 않음 — 철이 바뀐 값끼리 견줘 ▲178% 같은 숫자가 나왔음 */
              <div className="ai"><span>AI 1주 뒤 예측</span><b>{won(p.pred.predicted_price)}원</b><small className="muted">최근 거래가 없어 지금 값과 비교하지 않아요</small></div>
            ) : (
              <div className="ai"><span>AI 1주 뒤 예측</span><b>{won(p.pred.predicted_price)}원 {p.pred.change_pct >= 0 ? "▲" : "▼"} {Math.abs(p.pred.change_pct).toFixed(1)}%</b>{p.pred.base_price != null && <small className="muted">최근 7일 평균 {won(p.pred.base_price)}원 대비</small>}
                {/* 11-17: 작년보다 크게 오른 때는 예측이 낮게 나오기 쉬움 (예측 화면 ⚠️ 와 같은 기준) */}
                {p.pred.trend_vs_last_year >= 1.5 && <small className="muted">⚠️ 작년보다 {p.pred.trend_vs_last_year.toFixed(1)}배 높은 때라 예측이 낮게 나오기 쉬워요</small>}</div>
            ))}
            {!p.pred && p.season?.label && (
              // 11-17: 지금 거래는 있는데 1주 뒤 예측만 없는 때(예: 11월 딸기)도 '출하철 아님'이라 헷갈림 → 다음 예측 시작일을 보여 줌
              <div className="ai"><span>AI 예측</span><b>{p.season.next_start ? `${md(p.season.next_start)}부터 예측해요 · 주로 ${p.season.label}` : `출하철 아님 · 주로 ${p.season.label}`}</b></div>
            )}
          </Link>
        );
      })}
      <button type="button" className="mp-fav add" onClick={onAdd}>
        <b>+</b>관심 품목 {favorites.length ? "바꾸기" : "더하기"}<small>{favorites.length > FAV_SHOW ? `외 ${favorites.length - FAV_SHOW}개 더 있어요 · ` : ""}50개 품목에서 골라요</small>
      </button>
    </div>
  );
}

function Activity({ act }) {
  const [tab, setTab] = useState("posts");
  const rows = act?.[tab];
  return (
    <section className="card">
      <div className="mp-seg" role="tablist">
        <button role="tab" className={tab === "posts" ? "on" : ""} onClick={() => setTab("posts")}>내가 쓴 글{act?.posts && <em>{act.posts.length}</em>}</button>
        <button role="tab" className={tab === "comments" ? "on" : ""} onClick={() => setTab("comments")}>내가 쓴 댓글{act?.comments && <em>{act.comments.length}</em>}</button>
      </div>
      {act && rows == null && <p className="mp-empty">지금은 불러오지 못했어요. 잠시 뒤 다시 열어 주세요.</p>}
      {rows && !rows.length && <p className="mp-empty">아직 {tab === "posts" ? "쓴 글이" : "쓴 댓글이"} 없어요. <Link className="link" to="/board">게시판 가기 ›</Link></p>}
      <ul className="mp-list">
        {tab === "posts" && rows?.slice(0, 6).map((p) => (
          <li key={p.id}>
            <span className="badge">{p.category}</span>
            {p.status === "HIDDEN" ? <span title="관리자가 숨긴 글이라 다른 사람에게 보이지 않아요">{p.title} <em className="muted small">(숨김)</em></span> : <Link to={`/board/${p.id}`}>{p.title}</Link>}
            {p.comment_count > 0 && <span className="cmt">[{p.comment_count}]</span>}
            <span className="m">{boardDate(p.created_at)} · 조회 {p.views}</span>
          </li>
        ))}
        {tab === "comments" && rows?.slice(0, 6).map((c) => (
          <li key={c.id}>
            <Link to={`/board/${c.post_id}#c${c.id}`}>{c.body}</Link>
            <span className="m">{c.post_title} · {boardDate(c.created_at)}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Notifications({ list, reload }) {
  const { user } = useAuth();
  const nav = useNavigate();
  const open = async (n) => {
    if (!n.read) await markRead(user.id, n.id);
    reload();
    if (n.link) nav(n.link);
  };
  return (
    <section className="card">
      <div className="mp-head"><h2>알림</h2><button type="button" className="link" onClick={async () => { await markRead(user.id); reload(); }}>모두 읽음</button></div>
      {!list?.length && <p className="mp-empty">받은 알림이 없어요.</p>}
      <ul className="mp-noti">
        {(list ?? []).slice(0, 5).map((n) => (
          <li key={n.id} className={n.read ? "" : "unread"}>
            <button type="button" onClick={() => open(n)}>
              <i aria-hidden>{NOTIFY_TYPES[n.type]?.icon ?? "🔔"}</i>
              <span><b>{n.title}</b><small>{n.body} · {timeAgo(n.at)}</small></span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Settings({ onEdit }) {
  const { user, updateProfile } = useAuth();
  const notify = { ...Object.fromEntries(Object.keys(NOTIFY_TYPES).map((k) => [k, true])), ...user.notify };
  const kinds = Object.entries(NOTIFY_TYPES).filter(([k]) => AUCTION_ENABLED || k !== "auction");
  return (
    <section className="card">
      <div className="mp-head"><h2>{NOTIFY_ENABLED ? "내 정보 · 알림 설정" : "내 정보"}</h2><button type="button" className="link" onClick={onEdit}>수정 ›</button></div>
      <ul className="mp-set">
        <li><span>닉네임</span>{user.name}</li>
        <li><span>지역</span>{user.region || "-"}</li>
        <li><span>연락처</span>{user.phone ? user.phone.replace(/(\d{3})-?(\d{3,4})-?(\d{4})/, "$1-****-$3") : "-"}</li>
        {NOTIFY_ENABLED && kinds.map(([k, t]) => (
          <li key={k}>
            {t.label} 알림
            <button type="button" role="switch" aria-checked={!!notify[k]} aria-label={`${t.label} 알림`} className={`mp-tg ${notify[k] ? "on" : ""}`}
              onClick={() => updateProfile({ notify: { ...notify, [k]: !notify[k] } })} />
          </li>
        ))}
      </ul>
      <button type="button" className="mp-danger" onClick={onEdit}>회원 탈퇴</button>
    </section>
  );
}

export default function MyPage() {
  const { user } = useAuth();
  const seller = AUCTION_ENABLED && canSell(user);
  const [params, setParams] = useSearchParams();
  const edit = params.get("tab");
  const go = (k) => { setParams(k ? { tab: k } : {}, { replace: true }); window.scrollTo({ top: 0 }); };
  const act = useAsync(() => getMyActivity(user), [user.id]);
  const noti = useAsync(() => (NOTIFY_ENABLED ? getNotifications(user.id) : Promise.resolve([])), [user.id]);
  useEffect(() => onNotificationsChanged(noti.reload), [noti.reload]);
  const unread = (noti.data ?? []).filter((n) => !n.read).length;

  // 편집 화면 (내 정보 수정 · 관심 품목 고르기 · 경매)
  const EDIT = { profile: ["내 정보 수정", Profile], watch: ["관심 품목 고르기", FavoritePicker], ...(seller ? { auctions: ["내 경매", MyAuctions] } : {}), ...(AUCTION_ENABLED ? { bids: ["입찰 참여", MyBids] } : {}) };
  if (EDIT[edit]) {
    const [title, View] = EDIT[edit];
    return (
      <div className="page mp">
        <div className="page-head"><h1>{title}</h1><button type="button" className="btn" onClick={() => go(null)}>← 마이페이지</button></div>
        <View />
      </div>
    );
  }

  return (
    <div className="page mp">
      <section className="card mp-prof">
        <div className="mp-top">
          <div className="mp-ava" aria-hidden>{user.name?.[0] ?? "🧺"}</div>
          <div>
            <h1>{user.name}<small>{user.email}</small></h1>
            <div className="mp-tags">
              <span className="badge green">{USER_TYPE_LABEL[user.type]}</span>
              {user.region && <span className="badge">📍 {user.region}</span>}
              {user.farm_name && <span className="badge">{user.farm_name}</span>}
              {user.joined && <span className="badge">가입 {user.joined}</span>}
            </div>
          </div>
          <div className="mp-btns">
            {seller && <Link className="btn" to="/mypage/auctions/new">＋ 경매 등록</Link>}
            <button type="button" className="btn primary" onClick={() => go("profile")}>내 정보 수정</button>
          </div>
        </div>
        <div className={`mp-stats ${NOTIFY_ENABLED ? "" : "n3"}`}>
          <button type="button" onClick={() => go("watch")}><span>관심 품목</span><b>{(user.favorites ?? []).length}<small>개</small></b></button>
          {NOTIFY_ENABLED && <div><span>새 알림</span><b className={unread ? "new" : ""}>{unread}<small>개</small></b></div>}
          <div><span>내가 쓴 글</span><b>{act.data?.posts?.length ?? "-"}<small>개</small></b></div>
          <div><span>내가 쓴 댓글</span><b>{act.data?.comments?.length ?? "-"}<small>개</small></b></div>
        </div>
      </section>
      <div className="mp-grid">
        <div className="mp-col">
          <section className="card">
            <div className="mp-head"><h2>관심 품목 가격</h2><small>오늘 도매 시세 (직전 거래일 대비) · AI 1주 뒤 예측 (최근 7일 평균 대비)</small></div>
            <FavCards onAdd={() => go("watch")} />
          </section>
          <Activity act={act.data} />
        </div>
        <div className="mp-col">
          {NOTIFY_ENABLED && <Notifications list={noti.data} reload={noti.reload} />}
          <Settings onEdit={() => go("profile")} />
        </div>
      </div>
    </div>
  );
}

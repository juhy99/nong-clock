import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { getItems, predict } from "../api/ml";
import { NEWS_CATEGORIES, NEWS_PAGE_SIZE, getNews, getNewsTrend } from "../api/news";
import { useAuth } from "../components/AuthContext";
import { Async, PctChange, useAsync } from "../components/common";
import ItemImage from "../components/ItemImage";
import { NewsArticle, NewsSource, NewsTrend, NewsUpdated } from "../components/NewsParts";
import { dayLabel } from "../utils/format";

const ITEM_CHIPS = 8; // 나머지는 "+N" 을 눌러 펼친다

/** 기사를 날짜별로 묶는다 (오늘 · 어제 · 10월 18일 …) */
function byDay(rows) {
  const groups = [];
  for (const n of rows) {
    const key = new Date(n.published_at).toDateString();
    if (groups.at(-1)?.key !== key) groups.push({ key, label: dayLabel(n.published_at), rows: [] });
    groups.at(-1).rows.push(n);
  }
  return groups;
}

/** 오른쪽: 뉴스에 가장 많이 나온 품목의 AI 예측을 함께 */
function NewsWithForecast({ top }) {
  const p = useAsync(() => (top ? predict({ item: top.item, horizon: 7 }) : Promise.resolve(null)), [top?.item]);
  if (!top || !p.data) return null;
  const d = p.data;
  return (
    <div className="news-ai">
      <h3>{top.emoji} {top.name}, 뉴스와 예측을 같이 보면</h3>
      <p>
        이번 주 {top.name} 기사가 <b>{top.count}건</b>으로 가장 많아요. AI 예측은 다음 주 <PctChange value={d.change_pct} />이에요.
      </p>
      <Link className="btn primary sm" to={`/ai?item=${top.item}`}>AI 예측 보기</Link>
    </div>
  );
}

export default function News() {
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();
  const category = params.get("category") ?? "";
  const item = params.get("item") ?? "";
  const mine = params.get("mine") === "1" && !!user;
  const [size, setSize] = useState(NEWS_PAGE_SIZE);
  const [allChips, setAllChips] = useState(false);

  const go = (patch) => {
    const next = { category, item, mine: mine ? "1" : "", ...patch };
    setParams(Object.fromEntries(Object.entries(next).filter(([, v]) => v)));
    setSize(NEWS_PAGE_SIZE);
  };

  const favorites = user?.favorites ?? [];
  const items = useAsync(getItems);
  const trend = useAsync(() => getNewsTrend({ days: 7, limit: 5 }));
  const news = useAsync(
    () => getNews({ category, item, items: mine ? favorites : null, size }),
    [category, item, mine, size, favorites.join()],
  );
  const chips = allChips ? items.data ?? [] : (items.data ?? []).slice(0, ITEM_CHIPS);

  return (
    <div className="page">
      <div className="page-head news-head">
        <div>
          <h1>농업 뉴스</h1>
          <p>팜비드가 다루는 품목의 가격·기상·정책 기사를 모았어요. 기사 본문은 각 언론사 사이트에서 볼 수 있어요.</p>
        </div>
        {news.data && <NewsUpdated at={news.data.updated_at} />}
      </div>

      <div className="news-filters">
        <div className="tabs" role="tablist">
          {["", ...NEWS_CATEGORIES].map((c) => (
            <button key={c || "all"} role="tab" aria-selected={category === c} className={category === c ? "on" : ""} onClick={() => go({ category: c })}>
              {c || "전체"}
            </button>
          ))}
        </div>
        <div className="pills">
          <button className={`pill sm ${!item ? "on" : ""}`} onClick={() => go({ item: "" })}>전체 품목</button>
          {chips.map((i) => (
            <button key={i.code} className={`pill sm ${item === i.code ? "on" : ""}`} onClick={() => go({ item: item === i.code ? "" : i.code })}>
              <ItemImage code={i.code} emoji={i.emoji} className="xs" /> {i.name}
            </button>
          ))}
          {!allChips && (items.data?.length ?? 0) > ITEM_CHIPS && (
            <button className="pill sm" onClick={() => setAllChips(true)}>+{items.data.length - ITEM_CHIPS}</button>
          )}
          {user ? (
            <button className={`pill sm news-mine ${mine ? "on" : ""}`} onClick={() => go({ mine: mine ? "" : "1" })} disabled={!favorites.length} title={favorites.length ? "" : "마이페이지에서 관심 품목을 먼저 골라 주세요"}>
              ♡ 내 관심 품목만
            </button>
          ) : (
            <Link className="pill sm news-mine" to={`/login?next=${encodeURIComponent("/news?mine=1")}`}>♡ 로그인하면 관심 품목만 보기</Link>
          )}
        </div>
      </div>

      <div className="news-layout">
        <div>
          <Async state={news} empty="조건에 맞는 기사가 없어요" minHeight={300}>
            {(d) => (
              <>
                {d.rows.length === 0 && <div className="state">조건에 맞는 기사가 없어요</div>}
                {byDay(d.rows).map((g) => (
                  <section key={g.key}>
                    <h2 className="news-day">{g.label}</h2>
                    {g.rows.map((n) => <NewsArticle key={n.id} n={n} />)}
                  </section>
                ))}
                {d.total > d.rows.length && (
                  <div className="news-more">
                    <button className="btn" onClick={() => setSize(size + NEWS_PAGE_SIZE)}>기사 더 보기 ({d.rows.length}/{d.total})</button>
                  </div>
                )}
              </>
            )}
          </Async>
        </div>
        <aside className="news-side">
          <div className="news-box">
            <h3>이번 주 뉴스에 많이 나온 품목</h3>
            <p className="muted small">기사 제목·요약 기준 · 누르면 그 품목 기사만</p>
            {trend.data && <NewsTrend rows={trend.data} active={item} onPick={(c) => go({ item: item === c ? "" : c })} />}
          </div>
          <NewsWithForecast top={trend.data?.[0]} />
          <NewsSource />
        </aside>
      </div>
    </div>
  );
}

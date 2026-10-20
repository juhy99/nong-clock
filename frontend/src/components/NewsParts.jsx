// 농업 뉴스 부품. 홈 헤드라인·뉴스 페이지·통합 검색이 같이 쓴다.
// 기사는 제목·요약만 보여주고, 누르면 언론사 원문이 새 탭으로 열린다 (본문을 옮겨 오지 않는다 — 저작권).
import { Link } from "react-router-dom";
import { hourMinute, timeAgo } from "../utils/format";
import { Highlight } from "./common";

const CAT_CLASS = { "가격·수급": "price", "기상·재해": "wx", "정책·지원": "pol", "유통·경매": "dist" };

export const NewsCat = ({ category }) => <span className={`news-cat ${CAT_CLASS[category] ?? ""}`}>{category}</span>;

export const ItemTag = ({ tag }) => <Link to={`/news?item=${tag.item}`} className="news-item-tag">{tag.emoji} {tag.name}</Link>;

/** 한 줄 헤드라인 (홈·검색 미리보기) */
export function NewsRow({ n, q }) {
  return (
    <a className="news-row" href={n.url} target="_blank" rel="noreferrer">
      <NewsCat category={n.category} />
      <span className="t"><Highlight text={n.title} q={q} /></span>
      <span className="m">{n.press} · {timeAgo(n.published_at)} <i aria-hidden>↗</i></span>
    </a>
  );
}

/** 제목 + 요약 두 줄 + 품목 태그 (뉴스 페이지·검색 뉴스 탭) */
export function NewsArticle({ n, q, links = true }) {
  const first = n.item_tags[0];
  return (
    <article className="news-article">
      <a className="tt" href={n.url} target="_blank" rel="noreferrer">
        <Highlight text={n.title} q={q} /> <i aria-hidden>↗</i>
      </a>
      <p className="ds"><Highlight text={n.summary} q={q} /></p>
      <div className="mt">
        <NewsCat category={n.category} />
        {n.item_tags.map((t) => <ItemTag key={t.item} tag={t} />)}
        <span>{n.press} · {timeAgo(n.published_at)}</span>
        {links && first && (
          <Link className="go" to={n.category === "가격·수급" ? `/market?item=${first.item}` : `/ai?item=${first.item}`}>
            {n.category === "가격·수급" ? `📈 ${first.name} 시세 보기` : `🤖 ${first.name} AI 예측 보기`} ›
          </Link>
        )}
      </div>
    </article>
  );
}

/** 이번 주 뉴스에 많이 나온 품목 막대 */
export function NewsTrend({ rows, active, onPick }) {
  const max = Math.max(1, ...rows.map((r) => r.count));
  return (
    <div className="news-trend">
      {rows.map((r) => (
        <button key={r.item} className={`news-bar ${active === r.item ? "on" : ""}`} onClick={() => onPick(r.item)}>
          <span>{r.emoji} {r.name}</span>
          <span className="tr"><i style={{ width: `${(r.count / max) * 100}%` }} /></span>
          <span className="n">{r.count}건</span>
        </button>
      ))}
    </div>
  );
}

export const NewsUpdated = ({ at }) => <span className="news-updated">🔄 {hourMinute(at)} 업데이트 · 1시간마다</span>;

export const NewsSource = () => (
  <p className="news-source">뉴스 제공: 네이버 검색 API · 각 언론사. 제목과 요약 일부만 보여 주고, 기사 본문은 언론사 사이트에서 열려요. (지금은 화면 확인용 예시 기사)</p>
);

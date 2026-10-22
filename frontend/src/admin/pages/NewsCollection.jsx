import { useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { newsHealth } from "../../api/collection";
import { SectionHead } from "../../components/common";
import { ITEMS } from "../../mocks/catalog";
import { OTHER_CROPS } from "../../utils/itemMatch";
import { dateTime, timeAgo } from "../../utils/format";

const HEALTH_BADGE = { ok: "green", warn: "amber", bad: "red" };
const hm = (iso) => new Date(iso).toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit", hour12: false });

/** 최근 7일 기사의 품목·작물·분류별 건수 */
function countTags(articles) {
  const items = {}, crops = {}, cats = {};
  for (const a of articles) {
    a.items?.forEach((c) => (items[c] = (items[c] ?? 0) + 1));
    a.crops?.forEach((c) => (crops[c] = (crops[c] ?? 0) + 1));
    cats[a.category] = (cats[a.category] ?? 0) + 1;
  }
  const name = (c) => ITEMS.find((i) => i.code === c) ?? OTHER_CROPS[c] ?? { name: c, emoji: "🌱" };
  const sorted = (o) => Object.entries(o).sort((a, b) => b[1] - a[1]);
  return {
    items: sorted(items).map(([c, n]) => ({ ...name(c), n })),
    crops: sorted(crops).map(([c, n]) => ({ ...name(c), n })),
    cats: sorted(cats),
  };
}

function Bars({ rows, max }) {
  return (
    <div className="tag-bars">
      {rows.map((r) => (
        <div key={r.name} className="tag-bar">
          <span>{r.emoji} {r.name}</span>
          <span className="tr"><i style={{ width: `${(r.n / max) * 100}%` }} /></span>
          <span className="n num">{r.n}</span>
        </div>
      ))}
    </div>
  );
}

const tagName = (c) => {
  const t = ITEMS.find((i) => i.code === c) ?? OTHER_CROPS[c];
  return t ? `${t.emoji} ${t.name}` : c;
};

function Rejected({ rejected }) {
  const [q, setQ] = useState("");
  const [more, setMore] = useState(false);
  // 점수가 높은 것(아깝게 빠진 기사)부터: 놓친 농업 기사를 찾기 쉽게
  const rows = (rejected?.articles ?? []).filter((a) => !q || a.title.includes(q)).sort((a, b) => b.score - a.score);
  return (
    <div className="admin-sub">
      <div className="card-head" style={{ marginBottom: 0 }}>
        <div>
          <h3 style={{ margin: 0 }}>거른 기사 <span className="muted small">마지막 수집 {rejected?.collected_at ? dateTime(rejected.collected_at) : "-"} · {rejected?.articles?.length ?? 0}건</span></h3>
          <p className="small muted" style={{ margin: "2px 0 0" }}>
            농업 기사인데 빠졌다면 <code>shared/news_rules.json</code> 에 단어를 더하고 서버에서 <code>--relabel</code> (점수: 농업 단어 + · 잡음 단어 −)
          </p>
        </div>
        <input className="input" style={{ maxWidth: 200 }} placeholder="제목 검색" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      {rows.length === 0 ? (
        <p className="small muted" style={{ margin: 0 }}>{q ? "검색 결과가 없어요" : "거른 기사가 없어요"}</p>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead><tr><th className="r">점수</th><th>제목 <span className="muted small">점수 높은 순 (아깝게 빠진 기사부터)</span></th><th>잡힌 품목</th></tr></thead>
            <tbody>
              {rows.slice(0, more ? 200 : 10).map((a) => (
                <tr key={a.url}>
                  <td className="r num">{a.score}</td>
                  <td><a className="link" href={a.url} target="_blank" rel="noreferrer">{a.title}</a></td>
                  <td className="small muted">{[...(a.items ?? []), ...(a.crops ?? [])].map(tagName).join(" ") || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {!more && rows.length > 10 && <button className="btn sm" onClick={() => setMore(true)}>더 보기 ({rows.length - 10}건)</button>}
    </div>
  );
}

/** 관리자 › 데이터 수집 › 뉴스 수집 (collector/news 의 수집 기록·기사 파일) */
export default function NewsCollection({ news }) {
  const tags = useMemo(() => countTags(news.recent?.articles ?? []), [news]);
  if (news.error) {
    return (
      <section className="card">
        <SectionHead title="뉴스 수집" desc="collector/news · 1시간마다 · NAVER API HUB" />
        <p className="error" style={{ margin: 0 }}>{news.error}</p>
      </section>
    );
  }
  const { log, recent, rejected, sample } = news;
  const health = newsHealth(log);
  const runs = log.runs ?? [];
  const last = runs[0];
  const latestOk = runs.find((r) => r.ok);
  const interval = log.interval_min ?? 60;
  const next = last ? new Date(new Date(last.finished_at).getTime() + interval * 60000) : null;
  const recentRuns = runs.slice(0, 24).reverse();
  const failMark = Math.max(4, Math.round(Math.max(...recentRuns.map((r) => r.added + r.rejected), 0) * 0.15)); // 실패 회차는 빨간 짧은 막대
  const chart = recentRuns.map((r) => ({ t: hm(r.finished_at), 저장: r.added, 거름: r.rejected, 실패: r.ok ? 0 : failMark, ok: r.ok, at: r.finished_at }));
  const callsToday = runs.filter((r) => new Date(r.finished_at).toDateString() === new Date().toDateString()).reduce((s, r) => s + (r.calls ?? 0), 0);

  return (
    <section className="card">
      <SectionHead
        title={<>뉴스 수집 <span className={`badge ${HEALTH_BADGE[health.level]}`}>{health.label}</span>{sample && <span className="badge" style={{ marginLeft: 6 }}>예시 데이터</span>}</>}
        desc={sample ? "서버에 연결되지 않아 예시를 보여줘요 (frontend/.env 의 VITE_NEWS_URL)" : `collector/news · ${interval}분마다 · NAVER API HUB · ${health.detail}`}
      />
      <div className="stat-row">
        <div className="stat"><div className="muted small">마지막 수집</div><div className="v num">{last ? hm(last.finished_at) : "-"}</div><div className="small muted">{last ? timeAgo(last.finished_at) : ""}</div></div>
        <div className="stat"><div className="muted small">다음 수집 예정</div><div className="v num">{next ? hm(next.toISOString()) : "-"}</div><div className="small muted">{interval}분마다</div></div>
        <div className="stat"><div className="muted small">이번 수집</div><div className="v num">{last?.ok ? `+${last.added}` : "실패"}</div><div className="small muted">{last?.ok ? `받은 ${last.received} · 거름 ${last.rejected}` : `${last?.errors?.length ?? 0}개 검색어 오류`}</div></div>
        <div className="stat"><div className="muted small">보유 기사</div><div className="v num">{latestOk?.stored_total ?? "-"}</div><div className="small muted">최근 7일 {latestOk?.stored_recent ?? recent.count}건</div></div>
        <div className="stat"><div className="muted small">오늘 네이버 호출</div><div className="v num">{callsToday}</div><div className="small muted">월 한도 775,000</div></div>
      </div>

      {last && !last.ok && (
        <div className="error-box">
          <b>마지막 수집 실패 ({dateTime(last.finished_at)})</b>
          <ul>{last.errors.slice(0, 5).map((e) => <li key={e}>{e}</li>)}</ul>
          {/401|403/.test(last.errors.join()) && <span className="small">→ 서버 .env 의 NAVER_CLIENT_ID·SECRET 확인 후 <code>docker compose up -d news-collector</code></span>}
        </div>
      )}

      <div className="news-col-grid">
        <div>
          <h3 className="sub-title">최근 {chart.length}회 수집 <span className="muted small">새로 저장 · 거름</span></h3>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={chart} margin={{ top: 4, right: 4, left: -18, bottom: 0 }}>
              <CartesianGrid vertical={false} stroke="#eee" />
              <XAxis dataKey="t" tick={{ fontSize: 11 }} interval={3} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip
                formatter={(v, k, p) => (k === "실패" ? (p.payload.ok ? [null, null] : ["수집 실패", ""]) : [`${v}건`, k])}
                labelFormatter={(_, p) => (p?.[0] ? dateTime(p[0].payload.at) : "")}
              />
              <Bar dataKey="저장" stackId="a" fill="#1f9d55" />
              <Bar dataKey="거름" stackId="a" fill="#d6d5d0" />
              <Bar dataKey="실패" stackId="a" fill="#d93025" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
          <p className="small muted chart-key"><i className="k-ok" /> 새로 저장 <i className="k-rej" /> 거름 <i className="k-fail" /> 실패한 회차</p>
        </div>
        <div>
          <h3 className="sub-title">최근 7일 기사 {recent.count}건 <span className="muted small">품목별</span></h3>
          <Bars rows={tags.items.slice(0, 8)} max={tags.items[0]?.n ?? 1} />
          {tags.crops.length > 0 && <p className="small muted" style={{ margin: "8px 0 0" }}>기타 작물: {tags.crops.map((c) => `${c.emoji} ${c.name} ${c.n}`).join(" · ")}</p>}
          <div className="cat-chips">{tags.cats.map(([c, n]) => <span key={c} className="badge">{c} {n}</span>)}</div>
        </div>
      </div>

      <Rejected rejected={rejected} />
    </section>
  );
}

import { useState } from "react";
import { getHiddenNews, hideNews, unhideNews } from "../../api/adminOps";
import { clearNewsCache, getNews } from "../../api/news";
import { clearHiddenNewsCache } from "../../api/site";
import { Async, SectionHead, useAsync } from "../../components/common";

/**
 * 뉴스 관리 (11-17): 수집기가 잘못 넣은 기사(농산물과 상관없는 기사 등)를 사용자 사이트에서 숨김.
 * 수집 파일은 그대로 두고 주소만 DB(news_hidden)에 적어 화면에서 뺌 → 언제든 다시 보이게 할 수 있음.
 * 분류 규칙(shared/news_rules.json)을 고치는 일은 여기서 하지 않음 (수집기 코드 쪽)
 */
export default function NewsAdmin() {
  const [q, setQ] = useState("");
  const [word, setWord] = useState("");
  const [page, setPage] = useState(1);
  const [msg, setMsg] = useState(null);
  const news = useAsync(() => getNews({ q: word, page, size: 20 }), [word, page]);
  const hidden = useAsync(getHiddenNews);

  const reloadAll = () => { clearHiddenNewsCache(); clearNewsCache(); news.reload(); hidden.reload(); };
  async function hide(n) {
    const reason = prompt(`이 기사를 사용자 사이트에서 숨길까요?\n\n${n.title}\n\n사유 (선택)`, "");
    if (reason === null) return;
    try { await hideNews(n.url, n.title, reason); setMsg({ ok: true, text: "숨겼어요. 사용자 화면에는 1분 안에 반영돼요" }); reloadAll(); } catch (e) { setMsg({ ok: false, text: e.message }); }
  }
  async function unhide(url) {
    try { await unhideNews(url); setMsg({ ok: true, text: "다시 보이게 했어요" }); reloadAll(); } catch (e) { setMsg({ ok: false, text: e.message }); }
  }

  return (
    <>
      <h1>뉴스 관리</h1>
      {msg && <div className={`banner small ${msg.ok ? "info" : ""}`}><span>{msg.ok ? "✅" : "⚠️"}</span><div>{msg.text}</div></div>}
      <section className="card">
        <SectionHead title="지금 보이는 기사" desc="최근 7일 수집 기사 · 새 것부터. 농산물과 상관없는 기사는 [숨기기]"
          right={<form onSubmit={(e) => { e.preventDefault(); setPage(1); setWord(q); }} style={{ display: "flex", gap: 6 }}>
            <input className="input" style={{ maxWidth: 200 }} placeholder="제목 · 내용 찾기" value={q} maxLength={50} onChange={(e) => setQ(e.target.value)} /><button className="btn sm">찾기</button></form>} />
        <Async state={news}>
          {(d) => (
            <>
              <div className="table-wrap"><table className="table">
                <thead><tr><th>기사</th><th>분류 · 품목</th><th>언론사</th><th /></tr></thead>
                <tbody>{d.rows.map((n) => (
                  <tr key={n.url}>
                    <td><a className="link" href={n.url} target="_blank" rel="noreferrer"><b>{n.title}</b></a><div className="muted small">{(n.summary ?? "").slice(0, 90)}</div></td>
                    <td className="small">{n.category}<div className="muted">{(n.item_tags ?? []).map((t) => t.name).join(" · ") || (n.items ?? []).join(" · ")}</div></td>
                    <td className="small">{n.press}</td>
                    <td><button className="btn sm danger" onClick={() => hide(n)}>숨기기</button></td>
                  </tr>
                ))}</tbody>
              </table></div>
              <div style={{ display: "flex", gap: 8, alignItems: "center", justifyContent: "center", marginTop: 12 }}>
                <button className="btn sm" disabled={d.page <= 1} onClick={() => setPage(d.page - 1)}>‹ 앞</button>
                <span className="small num">{d.page} / {d.pages} · {d.total}건</span>
                <button className="btn sm" disabled={d.page >= d.pages} onClick={() => setPage(d.page + 1)}>뒤 ›</button>
              </div>
            </>
          )}
        </Async>
      </section>
      <section className="card">
        <SectionHead title={`숨긴 기사${hidden.data ? ` ${hidden.data.length}건` : ""}`} desc="사용자 사이트의 뉴스 · 홈 · 검색에서 안 보여요" />
        <Async state={hidden} empty="숨긴 기사가 없어요">
          {(rows) => (
            <div className="table-wrap"><table className="table">
              <thead><tr><th>기사</th><th>사유</th><th>숨긴 때</th><th /></tr></thead>
              <tbody>{rows.map((h) => (
                <tr key={h.url}><td><a className="link" href={h.url} target="_blank" rel="noreferrer">{h.title || h.url}</a></td><td className="small">{h.reason ?? "-"}</td>
                  <td className="small num">{h.created_at.slice(0, 16).replace("T", " ")}</td><td><button className="btn sm" onClick={() => unhide(h.url)}>다시 보이기</button></td></tr>
              ))}</tbody>
            </table></div>
          )}
        </Async>
      </section>
    </>
  );
}

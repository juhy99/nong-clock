import { useCallback, useEffect, useRef, useState } from "react";
import { getRefreshStatus, startRefresh, uploadWolbo } from "../../api/adminRefresh";
import { SectionHead } from "../../components/common";
import { dateTime } from "../../utils/format";

// 자료 이름 (collector/daily 의 collect_log.csv source)
const SOURCE = {
  auction: "경매 정산가격", kamis: "KAMIS 도·소매", warning: "기상특보", weather: "날씨 관측", fcst: "날씨 예보", holiday: "공휴일",
  sanji: "산지공판장", garak_inout: "가락 반입량", at_resv: "aT 출하예약", fx: "환율", policy: "수급 정책", db_load: "DB 넣기",
  kosis: "통계청", wolbo: "관측월보",
};
const JOB = { daily: "매일 갱신", monthly: "월 예측 만들기" };
const STATUS = { ok: ["성공", "green"], failed: ["실패", "red"], interrupted: ["중단됨", "amber"], running: ["실행 중", "blue"] };
const WOLBO = [["VC", "엽근채소"], ["VS", "양념채소"], ["VPO", "감자"], ["F", "과일"]];
const mins = (iso) => Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 60000));

/** 데이터 수집 화면 맨 위: 지금 갱신 · 월 예측 만들기 · 월보 PDF 올리기. 갱신 서비스가 꺼져 있어도 이 카드만 안내를 보이고 페이지는 그대로 */
export default function RefreshCard() {
  const [st, setSt] = useState(null);
  const [err, setErr] = useState(null);      // 상태를 못 읽음 (갱신 서비스 꺼짐 등)
  const [msg, setMsg] = useState(null);      // 버튼 결과 {tone, text}
  const [busy, setBusy] = useState(false);   // 버튼 누른 직후
  const [uploads, setUploads] = useState([]); // [{name, ok, text}]
  const fileRef = useRef(null);
  const alive = useRef(true);

  const load = useCallback(
    () =>
      getRefreshStatus().then(
        (d) => alive.current && (setSt(d), setErr(null)),
        (e) => alive.current && (setErr(e), setSt(null)),
      ),
    [],
  );
  const running = st?.running;
  useEffect(() => {
    alive.current = true;
    load();
    return () => {
      alive.current = false;
    };
  }, [load]);
  // 실행 중이면 5초마다, 아니면 1분마다 (자동 실행이 시작됐는지 보려고)
  useEffect(() => {
    const t = setInterval(load, running ? 5000 : 60000);
    return () => clearInterval(t);
  }, [load, running]);

  const start = async (job) => {
    setBusy(true);
    setMsg(null);
    try {
      await startRefresh(job);
      setMsg({ tone: "ok", text: `${JOB[job]}을 시작했어요. 끝날 때까지 이 화면을 닫아도 계속 돌아요.` });
    } catch (e) {
      setMsg({ tone: "bad", text: e.message });
    }
    await load();
    if (alive.current) setBusy(false);
  };

  const onFiles = async (e) => {
    const files = [...e.target.files];
    e.target.value = "";
    setUploads([]);
    for (const f of files) {
      let row;
      try {
        const r = await uploadWolbo(f);
        row = { name: r.saved ?? f.name, ok: true, text: "올렸어요" };
      } catch (x) {
        row = { name: f.name, ok: false, text: x.message };
      }
      if (!alive.current) return;
      setUploads((u) => [...u, row]);
    }
    load();
  };

  if (err)
    return (
      <section className="card">
        <SectionHead title="데이터 갱신" desc="가격 수집 → DB → 예측을 서버에서 바로 돌립니다" right={<button className="btn sm" onClick={load}>다시 확인</button>} />
        <div className="alert-band warn">⚠️ {err.message}</div>
      </section>
    );
  if (!st) return <section className="card"><p className="muted small" style={{ margin: 0 }}>갱신 상태를 불러오는 중…</p></section>;

  const last = st.history?.find((h) => h.status !== "running");
  const lastDaily = st.history?.find((h) => h.status === "ok");
  const off = busy || !!running || !st.data_ok;
  const bad = st.sources?.filter((s) => !s.ok) ?? [];
  return (
    <section className="card refresh-card">
      <SectionHead
        title="데이터 갱신"
        desc={`가격 수집 → DB → 예측을 서버에서 바로 돌립니다 · 자동 실행 ${st.schedule ? `매일 ${st.schedule}` : "꺼짐 (버튼으로만)"}`}
        right={<button className="btn sm" onClick={load}>다시 확인</button>}
      />
      {!st.data_ok && <div className="alert-band bad" style={{ marginBottom: 12 }}>🔴 자료 폴더가 연결되지 않았어요 — 서버 .env 의 NC_DATA_ROOT 를 확인해 주세요.</div>}
      {!running && st.alerts?.map((a) => (
        <div key={a.text} className={`alert-band ${a.level === "bad" ? "bad" : "warn"}`} style={{ marginBottom: 12 }} role="alert">{a.level === "bad" ? "🔴" : "⚠️"} {a.text}</div>
      ))}
      {running && (
        <div className="alert-band warn" style={{ marginBottom: 12 }} role="status">
          <span>⏳ <b>{JOB[running.job] ?? running.job}</b> 실행 중 — 지금: {running.step} · {mins(running.started_at)}분째</span>
          {running.line && <span className="small num refresh-line" title={running.line}>{running.line}</span>}
        </div>
      )}
      {msg && !running && <div className={`alert-band ${msg.tone === "bad" ? "bad" : "warn"}`} style={{ marginBottom: 12 }}>{msg.tone === "bad" ? "🔴" : "✅"} {msg.text}</div>}
      {msg?.tone === "bad" && running && <p className="small" style={{ margin: "0 0 12px", color: "var(--up)" }}>{msg.text}</p>}

      <div className="refresh-rows">
        <div className="refresh-row">
          <div>
            <b>매일 갱신</b>
            <div className="small muted">
              예측 기준일 <b className="num">{st.forecast_base ?? "없음"}</b> · 경매 자료 <b className="num">{st.ledger_last ?? "없음"}</b> 까지
              {lastDaily && <> · 마지막 성공 {dateTime(lastDaily.finished_at)}</>}
            </div>
            <div className="small muted">자료 받기(경매·KAMIS·특보·산지) → DB 표 만들기 → DB 에 넣기 → 예측 만들기 (약 20분)</div>
          </div>
          <button className="btn primary" disabled={off} onClick={() => start("daily")}>지금 갱신</button>
        </div>

        <div className="refresh-row">
          <div>
            <b>월 예측 (v4)</b>
            <div className="small muted">
              지금 쓰는 기준월 <b className="num">{st.v4_base ?? "없음"}</b> · {st.monthly.reason}
            </div>
            <div className="small muted">매달 3일 뒤 한 번. 월보 PDF 를 먼저 올려 두면 생산 전망이 반영돼요 (약 10분 + 매일 갱신)</div>
          </div>
          <button className="btn" disabled={off || !st.monthly.ready} title={st.monthly.ready ? "" : st.monthly.reason} onClick={() => start("monthly")}>월 예측 만들기</button>
        </div>

        <div className="refresh-row">
          <div>
            <b>관측월보 PDF</b> <span className="small muted">({st.wolbo.month} 호)</span>
            <div className="small" style={{ display: "flex", gap: 10, flexWrap: "wrap", marginTop: 4 }}>
              {WOLBO.map(([k, label]) => (
                <span key={k} title={`${k}${st.wolbo.month.replace("-", "")}….pdf`}>{st.wolbo.have[k] ? "✅" : "⬜"} {label} <span className="muted">({k})</span></span>
              ))}
            </div>
            <div className="small muted">KREI 농업관측센터(aglook.krei.re.kr)에서 받은 파일 그대로 — 이름이 VC·VS·VPO·F + 연월 6자리로 시작해야 해요</div>
            {uploads.length > 0 && (
              <ul className="small" style={{ margin: "6px 0 0", paddingLeft: 18 }}>
                {uploads.map((u, i) => <li key={i} style={u.ok ? undefined : { color: "var(--up)" }}>{u.ok ? "✅" : "❌"} {u.name} — {u.text}</li>)}
              </ul>
            )}
          </div>
          <div>
            <input ref={fileRef} type="file" accept="application/pdf,.pdf" multiple hidden onChange={onFiles} />
            <button className="btn" disabled={!st.data_ok} onClick={() => fileRef.current?.click()}>PDF 올리기</button>
          </div>
        </div>
      </div>

      {st.sources?.length > 0 && (
        <div className="small" style={{ marginTop: 14 }}>
          <span className="muted">마지막 수집 결과 </span>
          <span style={{ display: "inline-flex", gap: 8, flexWrap: "wrap", verticalAlign: "top" }}>
            {st.sources.map((s) => (
              <span key={s.source} className={`badge ${s.ok ? "green" : "red"}`} title={`${s.finished_at ? dateTime(s.finished_at) : ""}${s.error ? ` · ${s.error}` : ""}`}>
                {s.ok ? "✅" : "❌"} {SOURCE[s.source] ?? s.source}
              </span>
            ))}
          </span>
          {bad.length > 0 && <div className="muted" style={{ marginTop: 6 }}>❌ 표시는 못 받은 자료예요 (마우스를 올리면 이유).</div>}
          <div className="muted" style={{ marginTop: 6 }}>시세 화면과 예측이 읽는 자료만 받아요. 날씨는 날씨 수집기가 따로 받습니다 (아래 표).</div>
        </div>
      )}

      {last && (
        <details style={{ marginTop: 14 }} open={last.status !== "ok"}>
          <summary className="small">
            최근 실행 — {JOB[last.job] ?? last.job} <span className={`badge ${STATUS[last.status]?.[1] ?? ""}`}>{STATUS[last.status]?.[0] ?? last.status}</span>{" "}
            <span className="muted num">{dateTime(last.started_at)}{last.finished_at ? ` ~ ${dateTime(last.finished_at)}` : ""}</span>
            {last.failed_step && <> · 멈춘 단계: <b>{last.failed_step}</b></>}
          </summary>
          {last.tail?.length > 0 && <pre className="refresh-tail">{last.tail.join("\n")}</pre>}
          <table className="table" style={{ marginTop: 8 }}>
            <thead><tr><th>종류</th><th>시작</th><th>끝</th><th>결과</th></tr></thead>
            <tbody>
              {st.history.map((h) => (
                <tr key={h.started_at + h.job}>
                  <td>{JOB[h.job] ?? h.job}</td>
                  <td className="small num">{dateTime(h.started_at)}</td>
                  <td className="small num">{h.finished_at ? dateTime(h.finished_at) : "-"}</td>
                  <td><span className={`badge ${STATUS[h.status]?.[1] ?? ""}`}>{STATUS[h.status]?.[0] ?? h.status}</span>{h.failed_step ? <span className="small muted"> {h.failed_step}</span> : null}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      )}
    </section>
  );
}

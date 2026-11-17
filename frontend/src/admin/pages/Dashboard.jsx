import { Link } from "react-router-dom";
import { getAllAuctions } from "../../api/admin";
import { getNewsCollection, newsHealth } from "../../api/collection";
import { adminPosts, adminStats } from "../../api/adminBoard";
import { getFreshness, getOpsErrors, weekdaysSince } from "../../api/adminOps";
import { md } from "../../utils/format";
import { collectorHealth, getWeatherStatus, worstHealth } from "../../api/weather";
import { Async, useAsync } from "../../components/common";
import SystemStatus from "./SystemStatus";
import { AUCTION_ENABLED } from "../../features";

/**
 * 수집이 멈췄거나 실패 중이면 첫 화면 맨 위에 경고 (서버에 연결된 경우만)
 * 뉴스: 지연·실패·멈춤 / 예보: 실패·멈춤 (지난 발표는 다시 못 받아 급함) / 관측·전처리: 멈춤
 */
function CollectionAlert() {
  const state = useAsync(() =>
    Promise.all([getNewsCollection().catch(() => null), getWeatherStatus().catch(() => null)]).then(([news, weather]) => {
      const bands = [];
      if (news && !news.sample) bands.push(["뉴스 수집", newsHealth(news.log)]);
      if (weather?.collect) {
        const fcst = collectorHealth(weather.collect, "fcst");
        if (fcst.level !== "ok" && fcst.label !== "지연") bands.push(["예보 수집", fcst]);
        const obs = worstHealth([...["asos", "aws", "agri"].map((s) => collectorHealth(weather.collect, s)), weather.preprocess && collectorHealth(weather.preprocess, "preprocess")]);
        if (obs.level === "bad") bands.push(["관측 수집·전처리", obs]);
      }
      return bands.filter(([, h]) => h.level !== "ok");
    }),
  );
  return (state.data ?? []).map(([what, h]) => (
    <div key={what} className={`alert-band ${h.level}`} role="alert">
      <b>⚠️ {what} {h.label}</b>
      <span>{h.detail}</span>
      <Link className="link" to="/data">데이터 수집 보기 →</Link>
    </div>
  ));
}

/**
 * 자료 신선도 (11-17): 시세 · 예측이 며칠 것까지 들어왔나 + 서버 오류 횟수 (Spring /api/admin/ops/freshness · errors)
 * 초록 = 평일 1일 안 · 노랑 = 2~3일 · 빨강 = 그보다 오래됨 (도매시장 원장은 평일에 올라와 주말은 세지 않음)
 */
function Freshness() {
  const state = useAsync(() => Promise.all([getFreshness(), getOpsErrors().catch(() => null)]));
  const tone = (n) => (n == null ? "bad" : n <= 1 ? "ok" : n <= 3 ? "warn" : "bad");
  const DOT = { ok: "🟢", warn: "🟡", bad: "🔴" };
  return (
    <Async state={state}>
      {([f, err]) => {
        const rows = [
          ["도매 시세", f.price_last, "/data", "경매 원장이 들어온 마지막 거래일"],
          ["품종 시세", f.unit_last, "/data", "품종 · 작형별 시세"],
          ["소매가 (KAMIS)", f.retail_last, "/data", "소매 조사 가격"],
          ["예측 기준일", f.forecast_base, "/forecast", f.forecast_end ? `${f.forecast_end} 까지 예측` : "예측 표"],
        ].map(([label, date, to, desc]) => [label, date, to, desc, tone(weekdaysSince(date, f.today))]);
        if (f.forecast_base && f.price_last && f.forecast_base < f.price_last) rows[3][4] = "warn";   // 시세는 들어왔는데 예측을 아직 안 돌림
        return (
          <section className="card">
            <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
              {rows.map(([label, date, to, desc, t]) => (
                <Link key={label} to={to} className="stat" style={{ flex: "1 1 170px" }} title={desc}>
                  <div className="muted small">{DOT[t]} {label}</div>
                  <div className="v num">{date ? md(date) : "없음"}</div>
                  <div className="muted small">{date ? `평일 ${weekdaysSince(date, f.today)}일 전` : "표가 비어 있어요"}</div>
                </Link>
              ))}
              {err && (
                <Link to="/errors" className={`stat ${err.total.server ? "stat-amber" : ""}`} style={{ flex: "1 1 170px" }}>
                  <div className="muted small">{err.total.server ? "🔴" : "🟢"} 서버 오류 ({err.since_hours}시간)</div>
                  <div className="v num">{err.total.server}</div>
                  <div className="muted small">요청 제한 {err.total.limit} · 로그인 실패 {err.total.login}</div>
                </Link>
              )}
            </div>
            {f.forecast_base && f.price_last && f.forecast_base < f.price_last && (
              <p className="small" style={{ margin: "10px 0 0" }}>⚠️ 시세는 {md(f.price_last)}까지 들어왔는데 예측은 {md(f.forecast_base)} 기준이에요 — 예측 갱신을 돌려 주세요.</p>
            )}
          </section>
        );
      }}
    </Async>
  );
}

/** 관리자 첫 화면: 숫자 칸(게시판 · 회원) + 수집 경고 + 서버 상태. 신고는 기능을 뺐으므로 없음 (11-13) */
export default function Dashboard() {
  const state = useAsync(async () => {
    // 게시판 숫자 (11-14) · 회원 수 (11-17) 모두 실제 DB
    const [auctions, stats, recent, hidden] = await Promise.all([
      AUCTION_ENABLED ? getAllAuctions() : [], adminStats(), adminPosts({ page: 1 }), adminPosts({ status: "HIDDEN", page: 1 })]);
    const todayN = recent.rows.filter((p) => new Date(p.created_at).toDateString() === new Date().toDateString()).length;
    const live = auctions.filter((a) => a.status === "진행중" && new Date(a.ends_at) > new Date());
    return {
      tiles: [
        ...(AUCTION_ENABLED
          ? [
              ["승인 대기 경매", auctions.filter((a) => a.status === "승인대기").length, "/auctions", "amber"],
              ["진행 중 경매", live.length, "/auctions"],
            ]
          : []),
        ["오늘 올라온 글", todayN === recent.rows.length && recent.total > recent.rows.length ? `${todayN}+` : todayN, "/board"],
        ["전체 글", recent.total, "/board"],
        ["숨김 처리된 글", hidden.total, "/board", "amber"],
        ["회원", stats.members, "/members"],
        ["최근 7일 가입", stats.joined_7d, "/members"],
      ],
    };
  });

  return (
    <>
      <h1>대시보드</h1>
      <CollectionAlert />
      <Freshness />
      <Async state={state}>
        {(d) => (
          <>
            <div className="stat-row">
              {d.tiles.map(([label, v, to, tone]) => (
                <Link key={label} to={to} className={`stat ${tone && v > 0 ? `stat-${tone}` : ""}`}>
                  <div className="muted small">{label}</div>
                  <div className="v num">{v}</div>
                </Link>
              ))}
            </div>
          </>
        )}
      </Async>
      <SystemStatus />
    </>
  );
}

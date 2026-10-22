import { getCollectionStatus } from "../../api/admin";
import { Async, SectionHead, useAsync } from "../../components/common";
import { dateTime } from "../../utils/format";
import NewsCollection from "./NewsCollection";

const MODE = {
  server: ["서버 수집", "green"],
  test: ["테스트 모드", "amber"],
  file: ["파일", "blue"],
  none: ["미연결", ""],
};
const HEALTH_BADGE = { ok: "green", warn: "amber", bad: "red" };

// 보유 기간 막대: 2020-01-01 ~ 오늘
const AXIS_START = new Date("2020-01-01").getTime();
const YEARS = Array.from({ length: new Date().getFullYear() - 2019 }, (_, i) => 2020 + i);
const yearLeft = (y) => ((new Date(`${y}-01-01`).getTime() - AXIS_START) / (Date.now() - AXIS_START)) * 100;

function Coverage({ ranges, text }) {
  if (!ranges?.length) return <span className="small muted">{text ?? "-"}</span>;
  const now = Date.now();
  const pos = (t) => Math.min(100, Math.max(0, ((t - AXIS_START) / (now - AXIS_START)) * 100));
  const label = ranges.map(([a, b]) => `${a} ~ ${b ?? "오늘"}`).join(", ");
  return (
    <div className="coverage" title={label}>
      <div className="cov-bar">
        {ranges.map(([a, b]) => {
          const left = pos(new Date(a).getTime());
          const right = pos(b ? new Date(b).getTime() : now);
          return <i key={a} style={{ left: `${left}%`, width: `${Math.max(0.8, right - left)}%` }} />;
        })}
      </div>
      {text && <span className="small muted">{text}</span>}
    </div>
  );
}

function SourceStatus({ row }) {
  const [label, tone] = MODE[row.mode];
  if (row.health) return <span className={`badge ${HEALTH_BADGE[row.health.level]}`} title={row.health.detail}>{label} · {row.health.label}</span>;
  return <span className={`badge ${tone}`}>{label}</span>;
}

export default function DataStatus() {
  const state = useAsync(getCollectionStatus);
  return (
    <Async state={state}>
      {({ rows, news }) => (
        <>
          <section className="card">
            <SectionHead
              title="데이터 수집 현황"
              desc="원천별 수집 방식과 보유 기간. 서버 수집 = 팀 서버 컴퓨터가 계속 모음 · 테스트 모드 = 개발 중 화면이 그때그때 부름 · 파일 = 받은 자료"
              right={<button className="btn sm" onClick={state.reload} disabled={state.loading}>{state.loading ? "불러오는 중…" : "다시 불러오기"}</button>}
            />
            <div className="stat-row" style={{ marginBottom: 16 }}>
              {Object.entries(MODE).map(([mode, [label]]) => (
                <div key={mode} className="stat"><div className="muted small">{label}</div><div className="v">{rows.filter((r) => r.mode === mode).length}개</div></div>
              ))}
            </div>
            <div className="table-wrap">
              <table className="table data-sources">
                <thead>
                  <tr>
                    <th>데이터</th><th>주기</th><th>마지막 수집</th>
                    <th className="cov-head">보유 기간 <span className="cov-axis">{YEARS.map((y) => <span key={y} style={{ left: `${yearLeft(y)}%` }}>{String(y).slice(2)}</span>)}</span></th>
                    <th>상태</th><th>비고</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.key}>
                      <td><b>{r.source}</b><div className="small muted">{r.provider}</div></td>
                      <td className="small">{r.schedule}</td>
                      <td className="small num">{r.last_run ? dateTime(r.last_run) : "-"}</td>
                      <td><Coverage ranges={r.ranges} text={r.rangeText} /></td>
                      <td><SourceStatus row={r} /></td>
                      <td className="muted small">{r.note}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
          <NewsCollection news={news} />
        </>
      )}
    </Async>
  );
}

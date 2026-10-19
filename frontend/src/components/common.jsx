import { useCallback, useEffect, useState } from "react";
import { pct, shortDate, won } from "../utils/format";

/** API 호출 상태(로딩/에러/데이터)를 한 번에 관리 */
export function useAsync(fn, deps = []) {
  const [state, setState] = useState({ data: null, error: null, loading: true });
  const run = useCallback(() => {
    let alive = true;
    setState((s) => ({ ...s, loading: true, error: null }));
    fn()
      .then((data) => alive && setState({ data, error: null, loading: false }))
      .catch((error) => alive && setState({ data: null, error, loading: false }));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  useEffect(run, [run]);
  return { ...state, reload: run };
}

/** 로딩·에러·데이터 상태를 알아서 그려주는 감싸개 */
export function Async({ state, children, empty = "데이터가 없습니다", minHeight }) {
  if (state.loading && !state.data) return <div className="state" style={{ minHeight }}>불러오는 중…</div>;
  if (state.error)
    return (
      <div className="state error" style={{ minHeight }}>
        {state.error.message}
        <div style={{ marginTop: 10 }}>
          <button className="btn sm" onClick={state.reload}>다시 시도</button>
        </div>
      </div>
    );
  if (!state.data || (Array.isArray(state.data) && state.data.length === 0))
    return <div className="state" style={{ minHeight }}>{empty}</div>;
  return children(state.data);
}

/** ▲ 80원 (+6.9%) 10/16(금) 대비 — 비교 날짜를 반드시 함께 표기한다 */
export function PriceChange({ change, changePct, comparedDate, showAmount = true, className = "" }) {
  const dir = change > 0 ? "up" : change < 0 ? "down" : "flat";
  const arrow = change > 0 ? "▲" : change < 0 ? "▼" : "-";
  return (
    <span className={`${dir} num ${className}`}>
      {arrow} {showAmount && `${won(Math.abs(change))}원 `}({pct(changePct)})
      {comparedDate && <span className="muted small"> {shortDate(comparedDate)} 대비</span>}
    </span>
  );
}

/** 예측 변동률만 표시: ▲ 18.1% */
export function PctChange({ value, className = "" }) {
  const dir = value > 0 ? "up" : value < 0 ? "down" : "flat";
  return (
    <span className={`${dir} num ${className}`}>
      {value > 0 ? "▲" : value < 0 ? "▼" : "-"} {Math.abs(value).toFixed(1)}%
    </span>
  );
}

export function SectionHead({ title, desc, right }) {
  return (
    <div className="card-head">
      <div>
        <h2>{title}</h2>
        {desc && <p>{desc}</p>}
      </div>
      {right}
    </div>
  );
}

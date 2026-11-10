import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

/**
 * 오류 팝업 (11-10). 어디서든 const showError = useErrorPopup(); ... catch (e) { showError(e, { title: "글을 지우지 못했어요" }) }
 * - 큰 글씨: title (무엇이 안 됐는지), 그 아래: 서버가 보낸 문장(e.message), 그 아래: 왜 그런지·어떻게 하면 되는지(오류 종류별 설명)
 * - 오류 종류는 e.status (api/auth.js · api/board.js 가 서버 응답 코드를 붙임). 0 = 서버에 연결 못 함
 * - 로그인이 끝난 경우(401)에는 "로그인하러 가기" 버튼
 * 옵션: hints = { 401: "이 화면에서만 쓸 설명" } (예: 로그인 화면의 401 은 "비밀번호 확인"), login: false 면 로그인 버튼 숨김
 */
const ErrorCtx = createContext(() => {});

const HINTS = {
  0: "서버에 연결하지 못했어요. 인터넷 연결을 확인하고, 서버(Spring)가 켜져 있는지 확인한 뒤 다시 시도해 주세요.",
  400: "보낸 내용의 형식이 맞지 않아요. 입력한 내용을 확인하고 다시 시도해 주세요.",
  401: "로그인이 필요하거나 로그인 시간이 끝났어요. 다시 로그인해 주세요.",
  403: "이 작업을 할 수 있는 권한이 없어요. 본인이 쓴 글·댓글만 고치거나 지울 수 있어요.",
  404: "이미 지워졌거나 찾을 수 없어요. 화면을 새로고침해서 다시 확인해 주세요.",
  409: "이미 사용 중이에요. 다른 값으로 바꿔서 다시 시도해 주세요.",
  422: "입력한 내용이 규칙에 맞지 않아요. 위 안내대로 고쳐서 다시 시도해 주세요.",
  500: "서버에 문제가 생겼어요. 잠시 뒤 다시 시도해 주세요. 계속되면 관리자에게 알려 주세요.",
};

export function hintOf(err, hints = {}) {
  const s = err?.status;
  if (s != null && hints[s]) return hints[s];
  if (s != null && HINTS[s]) return HINTS[s];
  if (s >= 500) return HINTS[500];
  if (s >= 400) return HINTS[400];
  return "";
}

export function ErrorPopupProvider({ children }) {
  const [err, setErr] = useState(null); // { title, message, hint, login }
  const nav = useNavigate();
  const loc = useLocation();
  const okRef = useRef(null);

  const show = useCallback((e, { title = "문제가 생겼어요", hints, login = true } = {}) => {
    console.error(title, e); // 개발자 도구에서 자세히 볼 수 있게
    setErr({
      title,
      message: e?.message || "알 수 없는 오류가 발생했어요",
      hint: hintOf(e, hints),
      login: login && e?.status === 401 && loc.pathname !== "/login",
    });
  }, [loc.pathname]);

  const close = () => setErr(null);
  useEffect(() => {
    if (!err) return;
    okRef.current?.focus();
    const onKey = (ev) => ev.key === "Escape" && close();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [err]);

  return (
    <ErrorCtx.Provider value={show}>
      {children}
      {err && (
        <div className="modal-back" onMouseDown={(e) => e.target === e.currentTarget && close()}>
          <div className="modal err-pop" role="alertdialog" aria-modal="true" aria-labelledby="err-pop-title" aria-describedby="err-pop-msg">
            <h2 id="err-pop-title"><span aria-hidden>⚠️</span> {err.title}</h2>
            <p id="err-pop-msg" className="err-pop-msg">{err.message}</p>
            {err.hint && <p className="muted small err-pop-hint">{err.hint}</p>}
            <div className="err-pop-acts">
              {err.login && (
                <button type="button" className="btn" onClick={() => { close(); nav(`/login?next=${encodeURIComponent(loc.pathname + loc.search)}`); }}>
                  로그인하러 가기
                </button>
              )}
              <button type="button" className="btn primary" ref={okRef} onClick={close}>확인</button>
            </div>
          </div>
        </div>
      )}
    </ErrorCtx.Provider>
  );
}

/** 오류 팝업 띄우는 함수 */
export const useErrorPopup = () => useContext(ErrorCtx);

/** 화면을 불러오다 실패하면(useAsync 의 error) 팝업 한 번 */
export function usePopupOnError(error, title) {
  const show = useErrorPopup();
  useEffect(() => {
    if (error) show(error, { title });
  }, [error]); // eslint-disable-line react-hooks/exhaustive-deps
}

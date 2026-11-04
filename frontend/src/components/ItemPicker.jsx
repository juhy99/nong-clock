import { useEffect, useMemo, useRef, useState } from "react";

/**
 * 품목 선택 상자 (107개): 누르면 부류 탭 + 이름 검색 + 품목 칸이 열린다.
 * items: [{ code, name, category, emoji }] — 순서는 받은 그대로(거래 물량 순)
 */
export default function ItemPicker({ items, value, onChange, id = "item" }) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("전체");
  const box = useRef(null);
  const input = useRef(null);
  const cur = items.find((i) => i.code === value);
  const cats = useMemo(() => {
    const n = {};
    items.forEach((i) => (n[i.category] = (n[i.category] ?? 0) + 1));
    return [["전체", items.length], ...Object.entries(n)];
  }, [items]);
  const word = q.trim();
  const shown = items.filter((i) => (word ? i.name.includes(word) : cat === "전체" || i.category === cat));

  useEffect(() => {
    if (!open) return undefined;
    const close = (e) => !box.current?.contains(e.target) && setOpen(false);
    const esc = (e) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", esc);
    setTimeout(() => input.current?.focus(), 0);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", esc);
    };
  }, [open]);

  const pick = (code) => {
    onChange(code);
    setOpen(false);
    setQ("");
  };

  return (
    <div className="ip" ref={box}>
      <button id={id} type="button" className="input ip-btn" aria-haspopup="listbox" aria-expanded={open} onClick={() => setOpen(!open)}>
        <span>{cur ? <>{cur.emoji} <b>{cur.name}</b> <small className="muted">{cur.category}</small></> : "품목 고르기"}</span>
        <span className="muted">▾</span>
      </button>
      {open && (
        <div className="ip-pop" role="listbox">
          <input
            ref={input}
            className="input"
            placeholder={`품목 이름 검색 (${items.length}개)`}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && shown[0] && pick(shown[0].code)}
          />
          {!word && (
            <div className="ip-cats">
              {cats.map(([c, n]) => (
                <button key={c} type="button" className={`pill sm ${cat === c ? "on" : ""}`} onClick={() => setCat(c)}>
                  {c} <small>{n}</small>
                </button>
              ))}
            </div>
          )}
          <div className="ip-grid">
            {shown.map((i) => (
              <button key={i.code} type="button" role="option" aria-selected={i.code === value} className={`ip-item ${i.code === value ? "on" : ""}`} onClick={() => pick(i.code)}>
                <span className="ip-emo">{i.emoji}</span>
                <span>{i.name}</span>
              </button>
            ))}
            {!shown.length && <div className="muted small" style={{ padding: 12 }}>"{word}" 품목이 없어요</div>}
          </div>
        </div>
      )}
    </div>
  );
}

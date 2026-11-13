"""설계_모델비교_합치기_1112.md 의 후보 A~E 와 고르는 규칙 (월·일 공통)"""
import numpy as np, pandas as pd
W = np.round(np.arange(0, 1.01, 0.1), 1)

def score(df, col):   # 단위 평균 → 평균 (%)
    e = (np.exp(df[col] - df.xa) - 1).abs()
    return float(e.groupby(df.단위).mean().mean() * 100)

def med_acc(df, col):  # 팀원 잣대: 100 − 단위 평균 오차, 단위 중앙
    e = (np.exp(df[col] - df.xa) - 1).abs()
    return float(100 - e.groupby(df.단위).mean().median() * 100)

def blend(df, w):
    return w * df.xt + (1 - w) * df.xo

def fit_C(tr):
    s = [score(tr.assign(p=blend(tr, w)), "p") for w in W]; return W[int(np.argmin(s))]

def fit_D(tr):
    return {g: fit_C(tr[tr.grp == g]) for g in sorted(tr.grp.unique())}

def ap_D(te, ws, wC):
    w = te.grp.map(ws).fillna(wC); return w * te.xt + (1 - w) * te.xo

def fit_E(tr, wC):
    out = {}
    for u, g in tr.groupby("단위"):
        if len(g) < 6:
            out[u] = None; continue
        c = {"A": g.xt, "B": g.xo, "반반": 0.5 * g.xt + 0.5 * g.xo}
        out[u] = min(c, key=lambda k: float((np.exp(c[k] - g.xa) - 1).abs().mean()))
    return out

def ap_E(te, pick, wC):
    p = te.단위.map(pick)
    w = np.select([p == "A", p == "B", p == "반반"], [1.0, 0.0, 0.5], default=wC)
    return w * te.xt + (1 - w) * te.xo

def predict(name, tr, te):
    wC = fit_C(tr)
    if name == "A": return te.xt, None
    if name == "B": return te.xo, None
    if name == "C": return blend(te, wC), wC
    if name == "D": ws = fit_D(tr); return ap_D(te, ws, wC), ws
    if name == "E": pk = fit_E(tr, wC); return ap_E(te, pk, wC), pk

def run(df, label):
    """df: 단위, yr(목표 해), grp(거리 묶음), lt(팀원 log), lo(원인 log), la(실제 log)"""
    sel = df[df.yr.isin([2023, 2024])]; chk = df[df.yr >= 2025]
    rows = []
    for n in "ABCDE":
        cv = []
        for a, b in ((2023, 2024), (2024, 2023)):
            p, _ = predict(n, sel[sel.yr == a], sel[sel.yr == b]); cv.append(score(sel[sel.yr == b].assign(p=p), "p"))
        p_s, par = predict(n, sel, sel); p_c, _ = predict(n, sel, chk)
        rows.append(dict(후보=n, 교차점수=round(np.mean(cv), 2), 고르기=round(score(sel.assign(p=p_s), "p"), 2),
                         확인=round(score(chk.assign(p=p_c), "p"), 2), 확인_팀원잣대=round(med_acc(chk.assign(p=p_c), "p"), 1),
                         값=(par if not isinstance(par, dict) or n == "D" else f"{pd.Series(par).value_counts(dropna=False).to_dict()}")))
    R = pd.DataFrame(rows)
    order = list("ABCDE"); best = R.loc[R.교차점수.idxmin(), "후보"]
    for n in order:                     # 더 단순한 후보가 0.2%p 안이면 그쪽
        if R.set_index("후보").교차점수[n] <= R.set_index("후보").교차점수[best] + 0.2:
            best = n; break
    print(f"[{label}] 줄 {len(df):,} (고르기 {len(sel):,} · 확인 {len(chk):,}), 단위 {df.단위.nunique()}  → 고른 후보 {best}")
    print(R.to_string(index=False))
    return R, best

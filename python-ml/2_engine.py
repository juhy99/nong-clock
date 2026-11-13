"""2단계: 원인 모델 일 단위 엔진 (11-11) — 1단계 패널만 읽어 322단위를 매주 출발일마다 1~365일 뒤까지 예측

  python python-ml/2_engine.py [패널 폴더]        # 기본: model/ 의 가장 최근 panel_*
  python python-ml/2_engine.py <패널> 양파,복숭아   # 품목만 골라 빠르게 (시험용)
식 (변수표_원인모델_1111.md, 41·42번 stage42.py 와 같은 계산):
  log 예측 = 작년 같은 철 평균 + a + e × d̂ + 모양        (S0)
           = 작년 같은 철 평균 + a + 모양                 (MA)
           S0 + 과수는 d̂ 에 X4(여름 태풍특보) 항을 더함    (X4, 38번)
만드는 것 (model/run_<기준일>/):
  test_errors.csv        단위 × 모델 × 구간(고르기 목표 2023~24 · 확인 2025~) × 거리(1~30·31~90·91~365일): 오차 합·줄 수 (+ 작년 같은 날 기준선)
  test_monthly.csv       달 마지막 출발일 → 1~12달 뒤 목표월 평균 (42번 월 파일과 맞춰 보기용)
  forecast_unit_daily.csv.gz  마지막 출발일 → 1~365일 뒤 단위별 예측(원/kg) + 범위(고르기 구간 오차 10·90%)
가격은 '작년 같은 철 평균'(출발점)과 '모양'(기준점), 정답에만 쓴다. 지금 시세(v6)는 쓰지 않는다.
"""

import sys
from pathlib import Path

import os
import numpy as np
import pandas as pd

# 11-13 (팀원 시험·팀장 결정): 원인 모델의 a 항(과거 가격이 해마다 평균 몇 % 변했나)을 0 으로. 확인 구간 오차 1.4%p 좋아짐.
# 예전처럼 a 를 쓰려면 환경 변수 NC_KEEP_A=1
KEEP_A = os.getenv("NC_KEEP_A") == "1"

import config as C

H = 365
BUCKETS = ((1, 30), (31, 90), (91, 365))


# ───────── 날짜 격자 · 시세 (stage42 의 eng.py 와 같음) ─────────
class Grid:
    def __init__(self, end):
        self.day0 = pd.Timestamp("2020-01-01")
        self.days = pd.date_range(self.day0, end)
        self.N = len(self.days)
        d = self.days
        self.doy = np.array([(x.dayofyear - 1 if not (x.is_leap_year and x.dayofyear > 59) else x.dayofyear - 2) for x in d])
        self.yr = d.year.values

    def idx(self, ts):
        return (pd.Timestamp(ts) - self.day0).days

    def qa(self, df):
        q = np.zeros(self.N); a = np.zeros(self.N)
        i = ((pd.to_datetime(df.date) - self.day0).dt.days).values
        ok = (i >= 0) & (i < self.N)
        np.add.at(q, i[ok], df.volume_kg.values.astype(float)[ok]); np.add.at(a, i[ok], df.amount_won.values.astype(float)[ok])
        return q, a

    def prep(self, q, a):
        """7일 가격(금액 합 ÷ 물량 합)의 log, 그날 거래 여부"""
        N = self.N
        c = np.concatenate([[0], np.cumsum(q)]); ca = np.concatenate([[0], np.cumsum(a)])
        lo = np.maximum(np.arange(N) - 6, 0); q7 = c[np.arange(N) + 1] - c[lo]; a7 = ca[np.arange(N) + 1] - ca[lo]
        L = np.where(q7 > 0, np.log(np.where(q7 > 0, a7, 1) / np.where(q7 > 0, q7, 1)), np.nan)
        return L, q > 0

    def curve(self, L, tr, Y):
        """Y년 1월 1일 기준, 그 전 해들로 계절 곡선 (해마다 평균을 뺀 편차를 날짜별로 모아 ±10일로 폄)"""
        devs = []
        for y in range(2020, Y):
            m = (self.yr == y) & tr & ~np.isnan(L)
            if m.sum() < 60:
                continue
            s = np.zeros(365); n = np.zeros(365)
            np.add.at(s, self.doy[m], L[m] - L[m].mean()); np.add.at(n, self.doy[m], 1)
            devs.append((s, n))
        if len(devs) < 2:
            return None
        S = sum(d[0] for d in devs); Nn = sum(d[1] for d in devs)
        k = np.arange(-10, 11)
        S2 = np.array([S[(np.arange(365) + j) % 365] for j in k]).sum(0); N2 = np.array([Nn[(np.arange(365) + j) % 365] for j in k]).sum(0)
        return np.where(N2 >= 5, S2 / np.maximum(N2, 1), np.nan)


# ───────── 연 계수 (stage42 coefs · group_coef 와 같음) ─────────
def ridge(X, y, lam):
    mu = X.mean(0); sd = X.std(0); sd[sd < 1e-9] = 1; Z = (X - mu) / sd
    b = np.linalg.solve(Z.T @ Z + lam * np.eye(Z.shape[1]), Z.T @ (y - y.mean()))
    return b / sd, y.mean() - (mu / sd) @ b


class Coefs:
    def __init__(self, sy, su):
        A = sy.rename(columns={"supply_unit": "item", "year": "H"}).sort_values(["item", "H"]).reset_index(drop=True)
        A["되돌림2"] = A.groupby("item")["되돌림"].shift(1)
        self.A = A
        self.AI = {k: g.set_index("H") for k, g in A.groupby("item")}
        self.UGRP = {r.supply_unit: r.group_ugrp for r in su.itertuples() if r.in_prescription == 1}
        self.NGRP = {r.supply_unit: r.group_ngrp for r in su.itertuples() if r.group_ngrp}
        self.PUB = {r.supply_unit: (r.pub_year, int(r.pub_month)) for r in su.itertuples()}
        self.C, self.G = {}, {}

    def pub(self, item, y):
        """y년(작물 해) 생산량을 쓸 수 있는 첫날"""
        w, m = self.PUB.get(item, ("다음 해", 4))
        return pd.Timestamp(y + (1 if w == "다음 해" else 0), m, 1)

    def coefs(self, unit, Y):
        if (unit, Y) in self.C:
            return self.C[(unit, Y)]
        A = self.A
        x = A[(A["item"] == unit) & (A.H < Y) & A.dq.notna()]
        r = None
        if len(x) >= 8:
            r = {}
            t2 = x[x.dp.notna()]
            if len(t2) >= 8:
                q = t2.dq.values; p = t2.dp.values
                e = np.cov(q, p)[0, 1] / (np.var(q) * 1.01 + 1e-9); r["a"] = p.mean() - e * q.mean(); r["e"] = e; r["own_e"] = True
            else:
                g = self.group(self.NGRP.get(unit, self.UGRP.get(unit, "")), Y); r["a"], r["e"], r["own_e"] = g["a"], g["e"], False
            for nm, cols in (("S0", ["되돌림"]), ("S0b", ["되돌림2"])):
                xx = x.copy()
                for c in cols:
                    xx[c] = xx[c].fillna(0)
                b, c0 = ridge(xx[cols].values.astype(float), xx.dq.values, 3.0); r[nm] = (cols, b, c0)
        self.C[(unit, Y)] = r
        return r

    def group(self, grp, Y):
        if (grp, Y) in self.G:
            return self.G[(grp, Y)]
        us = [u for u, g in self.UGRP.items() if g == grp] or list(self.UGRP)
        cs = [self.coefs(u, Y) for u in us]; cs = [c for c in cs if c and c.get("own_e")]
        if not cs:
            cs = [c for c in (self.coefs(u, Y) for u in self.UGRP) if c and c.get("own_e")]
        self.G[(grp, Y)] = dict(a=float(np.median([c["a"] for c in cs])), e=float(np.median([c["e"] for c in cs])))
        return self.G[(grp, Y)]


class X4:
    """38번 X4: d̂ + b × (그해 여름 태풍특보 − 학습 평균). b 는 과수 공급 단위를 합쳐 (dq − 단위 평균) ~ 되돌림 + 특보 릿지, H ≤ y−2"""

    def __init__(self, sy, x4):
        P = sy[["supply_unit", "year", "dq", "되돌림"]].merge(x4, on=["supply_unit", "year"], how="inner")
        P["되돌림"] = P["되돌림"].fillna(0)
        self.P = P[P.dq.notna() & np.isfinite(P.dq)]
        self.V = {k: g.set_index("year").x4 for k, g in x4.groupby("supply_unit")}
        self.cache = {}

    def coef(self, y):
        if y in self.cache:
            return self.cache[y]
        G = self.P[self.P.year <= y - 2]
        r = None
        if len(G) >= 15:
            mu = G.groupby("supply_unit").dq.transform("mean"); X = G[["되돌림", "x4"]].values.astype(float); yy = (G.dq - mu).values
            m_ = X.mean(0); sd = X.std(0); sd[sd < 1e-9] = 1; Z = (X - m_) / sd
            b = np.linalg.solve(Z.T @ Z + 3.0 * np.eye(2), Z.T @ (yy - yy.mean())) / sd
            r = (float(b[1]), float(G.x4.mean()))
        self.cache[y] = r
        return r

    def term(self, su, y, day):
        """그해 여름(6~8월)이 끝난 다음 달(9월 1일)부터만"""
        if su not in self.V or y not in self.V[su].index or day < pd.Timestamp(y, 9, 1):
            return 0.0
        cb = self.coef(y)
        return 0.0 if cb is None else cb[0] * (float(self.V[su].loc[y]) - cb[1])


def main(panel=None, only_items=None, hook=None):
    """hook(un, G, o, Tt, h, lv, L, tr, Cb, meth): 실험용 — 출발일마다 예측을 받아 따로 셈 (python-ml/exp_*.py)"""
    if panel is None:
        panel = sorted(C.model_dir().glob("panel_*"))[-1]
    panel = Path(panel)
    base = pd.Timestamp(panel.name.split("_")[1])
    G = Grid(base + pd.Timedelta(days=H + 7))
    ud = pd.read_csv(panel / "unit_daily.csv.gz"); idaily = pd.read_csv(panel / "item_daily.csv.gz")
    sy = pd.read_csv(panel / "supply_yearly.csv"); x4 = pd.read_csv(panel / "x4_yearly.csv")
    us = pd.read_csv(panel / "unit_supply.csv", keep_default_na=False)
    shp = pd.read_csv(panel / "unit_shape_v3b.csv", keep_default_na=False).set_index("unit_name")
    su = pd.read_csv(panel / "supply_unit_v3b.csv", keep_default_na=False)
    vu = pd.read_csv(panel / "units.csv")
    item_of = dict(zip(vu.unit_name, vu.item_code))
    CF = Coefs(sy, su); XX = X4(sy, x4)
    BKI = np.array([0 if h <= 30 else (1 if h <= 90 else 2) for h in range(0, H + 2)])
    # 출발일: 2023-01-01(일)부터 7일마다, 기준일까지
    ORIG = np.arange(G.idx("2023-01-01"), G.idx(base) + 1, 7)
    if ORIG[-1] != G.idx(base):   # 11-12 운영: 마지막 출발일 = 기준일 (앞으로 예측이 기준일 다음 날부터 365일). 시험 줄은 그대로 (이 출발일엔 정답이 아직 없음)
        ORIG = np.append(ORIG, G.idx(base))
    last_o = ORIG[-1]
    MON = np.array([(d.year - 2000) * 12 + d.month for d in G.days])
    om = MON[ORIG]; ME = {int(ORIG[i]) for i in range(len(ORIG)) if i == len(ORIG) - 1 or om[i] != om[i + 1]}
    ICACHE = {}
    err_rows, mon_rows, fc_rows = [], [], []
    units = us.drop_duplicates("unit_name")
    if only_items:
        units = units[units.item_name.isin(only_items)]
    for k, ur in enumerate(units.itertuples()):
        un, it = ur.unit_name, ur.item_name
        uid = int(ur.unit_id)
        q, a = G.qa(ud[ud.unit_id == uid])
        if q.sum() == 0:
            continue
        L, tr = G.prep(q, a)
        ic = item_of[un]
        if ic not in ICACHE:
            qi, ai = G.qa(idaily[idaily.item_code == ic]); ICACHE[ic] = G.prep(qi, ai)
        LI, trI = ICACHE[ic]
        seas = [(r.supply_unit or None, int(r.season_start), int(r.season_months)) for r in us[us.unit_name == un].itertuples()]
        grp = shp.loc[un, "engine_group"]
        meth = [shp.loc[un, c] for c in ("방식_1_30", "방식_31_90", "방식_91_365")]
        model = ur.model; use_x4 = int(ur.x4_typhoon) == 1
        for Y in range(2023, base.year + 1):
            Cown = G.curve(L, tr, Y); CI = G.curve(LI, trI, Y)
            Cb = [(CI if "품목" in m else Cown) for m in meth]; Cb = [c if c is not None else CI for c in Cb]
            if any(c is None for c in Cb):
                continue
            Cs = Cb[2]; gc = CF.group(grp, Y)
            for o in ORIG[G.yr[ORIG] == Y]:
                Tt = o + np.arange(1, H + 1); Tt = Tt[Tt < G.N]; h = Tt - o; b = BKI[h]
                lv = {m: np.full(len(Tt), np.nan) for m in ("MA", "S0", "X4")}
                day_o = G.days[o]
                for (aunit, m0, n) in seas:
                    for y in range(Y - 1, Y + 2):
                        st = pd.Timestamp(y, m0, 1); en = st + pd.DateOffset(months=n); s0, s1 = G.idx(st), G.idx(en)
                        if day_o < st - pd.Timedelta(days=182) or en <= day_o:
                            continue
                        sel = (Tt >= s0) & (Tt < s1)
                        if not sel.any():
                            continue
                        a0, a1 = G.idx(st - pd.DateOffset(years=1)), G.idx(en - pd.DateOffset(years=1))
                        if a0 < 0:
                            continue
                        ii = np.arange(max(a0, 0), min(a1, o + 1)); ii = ii[tr[ii] & ~np.isnan(L[ii])]
                        if len(ii) < 20:
                            continue
                        p1 = (L[ii].mean(), np.nanmean(Cs[G.doy[ii]]))
                        shape = Cs[G.doy[Tt[sel]]] - p1[1]
                        cf = CF.coefs(aunit, y - 1) if aunit else None  # 학습은 H ≤ y−2
                        if cf:
                            aa, ee = (cf["a"] if KEEP_A else 0.0), cf["e"]   # 11-13: a(해마다 평균 가격 변화) = 0 — 가격 추세 항이라 원칙(가격은 기준점만)상 뺌
                            row = CF.AI[aunit].loc[y] if aunit in CF.AI and y in CF.AI[aunit].index else None
                            val = lambda c: np.nan if row is None or pd.isna(row[c]) else float(row[c])
                            lv["MA"][sel] = p1[0] + aa + shape
                            if day_o >= CF.pub(aunit, y - 1) and not np.isnan(val("되돌림")):
                                _, b0, k0 = cf["S0"]; d = k0 + b0[0] * val("되돌림")
                            elif day_o >= CF.pub(aunit, y - 2) and not np.isnan(val("되돌림2")):
                                _, b2, k2 = cf["S0b"]; d = k2 + b2[0] * val("되돌림2")
                            else:
                                d = 0.0
                            lv["S0"][sel] = p1[0] + aa + ee * d + shape
                            lv["X4"][sel] = p1[0] + aa + ee * (d + (XX.term(aunit, y, day_o) if use_x4 else 0.0)) + shape
                        else:
                            for m in lv:
                                lv[m][sel] = p1[0] + (gc["a"] if KEEP_A else 0.0) + shape
                pick = {"S0": "X4" if use_x4 else "S0", "MA": "MA"}[model]
                lv["선택"] = lv[pick]
                if hook is not None:
                    hook(un, G, o, Tt, h, lv, L, tr, Cb, meth)
                # 작년 같은 날 기준선 (364일 전 7일 가격)
                ly = np.where(Tt - 364 >= 0, L[np.maximum(Tt - 364, 0)], np.nan)
                act = np.where(tr[Tt], L[Tt], np.nan)
                ok = ~np.isnan(act) & ~np.isnan(lv["MA"])
                if ok.any():
                    per = np.where(G.yr[Tt] <= 2024, "고르기", "확인")
                    for m in ("MA", "S0", "X4", "선택"):
                        e = np.abs(np.exp(lv[m] - act) - 1)
                        for bi in range(3):
                            for pn in ("고르기", "확인"):
                                mm = ok & (b == bi) & (per == pn) & ~np.isnan(e)
                                if mm.any():
                                    err_rows.append((un, m, pn, bi, float(e[mm].sum()), int(mm.sum()), float(np.nanmedian(np.exp(lv[m][mm] - act[mm]) - 1))))
                    el = np.abs(np.exp(ly - act) - 1)
                    for bi in range(3):
                        for pn in ("고르기", "확인"):
                            mm = ok & (b == bi) & (per == pn) & ~np.isnan(el)
                            if mm.any():
                                err_rows.append((un, "작년같은날", pn, bi, float(el[mm].sum()), int(mm.sum()), np.nan))
                if o in ME:   # 달 마지막 출발일 → 1~12달 뒤 목표월 평균 (42번 월 파일과 같은 방식)
                    tm = MON[Tt]
                    for kk in range(1, 13):
                        jj = np.where(tm == MON[o] + kk)[0]
                        if len(jj) == 0:
                            continue
                        r = dict(예측단위=un, 출발=G.days[o].date(), 목표월=str(G.days[Tt[jj[0]]].to_period("M")), k=kk)
                        for m in ("MA", "S0", "X4", "선택"):
                            v = lv[m][jj]; r[m] = float(np.exp(np.nanmean(v))) if np.isfinite(v).any() else np.nan
                        aj = jj[tr[Tt[jj]] & (q[Tt[jj]] > 0)]
                        r["실제"] = float(np.exp(L[Tt[aj]]).mean()) if len(aj) >= 5 else np.nan
                        mon_rows.append(r)
                if o == last_o:
                    for j in np.where(np.isfinite(lv["선택"]))[0]:
                        fc_rows.append((uid, un, G.days[o].date(), G.days[Tt[j]].date(), int(h[j]), float(np.exp(lv["선택"][j])), pick))
        if (k + 1) % 20 == 0:
            print(f"  {k + 1}/{len(units)} 단위", flush=True)
    out = C.model_dir() / f"run_{base:%Y%m%d}"
    out.mkdir(parents=True, exist_ok=True)
    E = pd.DataFrame(err_rows, columns=["예측단위", "모델", "구간", "거리", "오차합", "줄", "치우침_중앙"])
    E["거리"] = E["거리"].map({0: "1~30일", 1: "31~90일", 2: "91~365일"})
    E.to_csv(out / "test_errors.csv", index=False, encoding="utf-8-sig")
    M = pd.DataFrame(mon_rows); M.to_csv(out / "test_monthly.csv", index=False, encoding="utf-8-sig")
    F = pd.DataFrame(fc_rows, columns=["unit_id", "unit_name", "base_date", "target_date", "h", "price", "model"])
    F.to_csv(out / "forecast_unit_daily.csv.gz", index=False, encoding="utf-8", compression="gzip")
    print(f"→ {out}  (시험 줄 {len(E):,}, 월 줄 {len(M):,}, 앞으로 예측 {len(F):,}줄, 마지막 출발일 {G.days[last_o].date()})")
    return E, M, F


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None, sys.argv[2].split(",") if len(sys.argv) > 2 else None)

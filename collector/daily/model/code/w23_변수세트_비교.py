# -*- coding: utf-8 -*-
"""(w23: NC_FEAT 로 변수 세트 고름. dropsigH = 17변수 + 명절 4개, w36)
70 w16b — 기능별 모델 비교 (최대 확장 패널 628계열·194품목, 가격 입력 금지)
기능 ① 출하량(생산) 예측 1~12개월  ② 단가 예측 1~12개월  ③ 급등·급락 경보(목표달 단가가 계절평균보다 ±25% 넘게 벗어남)
모델: 기준선(작년 같은 달 / 2년 평균 / 계절평균) · 선형(릿지) · 랜덤포레스트 · LightGBM · 앙상블
변수는 w1과 같음(기준월 t에 알 수 있는 물량·달력·품목·수입·날씨·면적생산), 가격은 정답·기준선에만
시험: 목표월 2023 / 2024 / 2025~ (학습은 그 해 1월 전 목표월 줄만)"""
import os, sys, time, numpy as np, pandas as pd, lightgbm as lgb, warnings; warnings.filterwarnings('ignore')
from pathlib import Path
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.linear_model import Ridge, LogisticRegression
from sklearn.metrics import roc_auc_score
R = os.environ.get('NC_R', str(Path(__file__).resolve().parents[2]) + '/'); OUTD = Path(os.environ.get('NC_OUT', Path(__file__).resolve().parents[1]))
P26 = R + '26_품종구분_전처리_변수/'
P = pd.read_csv(OUTD / '_입력' / '01x_품종월_패널_최대확장.csv.gz', dtype={'품목코드4': str})
P['ym'] = pd.PeriodIndex(P.연월, freq='M'); P['mi'] = P.ym.dt.year * 12 + P.ym.dt.month - 1
P['lq'] = np.log1p(P.q); P['lp'] = np.log(P.p)
K = P.계열키.unique(); kid = {k: i for i, k in enumerate(K)}; P['kid'] = P.계열키.map(kid)
T0 = P.mi.min(); T1 = P.mi.max(); n = T1 - T0 + 1
Q = np.full((len(K), n), np.nan); PR = np.full((len(K), n), np.nan)
Q[P.kid, P.mi - T0] = P.lq; PR[P.kid, P.mi - T0] = P.lp
qraw = np.expm1(Q)
# 품목 합(대상 품종 합) — 품목 단위 흐름
itm = P.groupby('계열키').품목코드4.first().reindex(K).values; items = pd.unique(itm)
IQ = np.vstack([np.nansum(np.where(np.isnan(qraw[itm == i]), 0, qraw[itm == i]), axis=0) for i in items]); iid = {i: j for j, i in enumerate(items)}
# 수입(품목, 26번 품목전체 수입_kg, 2020~)
d = pd.read_csv(P26 + '02_구분_시계열/02_월별_계열_물량단가.csv.gz', dtype={'품목코드4': str}, usecols=['계열키', '연월', '품목코드4', '수입_kg', '구분'], low_memory=False)
d = d[d.구분 == '품목전체']; d['품목코드4'] = d.품목코드4.str.zfill(4); d['mi'] = pd.PeriodIndex(d.연월, freq='M').year * 12 + pd.PeriodIndex(d.연월, freq='M').month - 1
IM = np.full((len(items), n), np.nan)
for i, j in iid.items():
    x = d[(d.품목코드4 == i) & d.mi.between(T0, T1)]; IM[j, x.mi - T0] = x.수입_kg.values
# 날씨·생산 (26번, 계열 × 연월)
FEAT = os.environ.get('NC_FEAT', 'base'); P84 = R + '00_기본자료/02_전처리/84_품종_날씨생산_628확장/'; P83 = R + '00_기본자료/02_전처리/83_품종_월보생산전망_신호/'
w = pd.read_csv(P84 + '01_계열_월별_산지가중날씨_628.csv.gz' if FEAT in ('ext84', 'sig') else P26 + '03_변수_날씨/01_계열_월별_산지가중날씨.csv.gz'); w = w[w.계열키.isin(K)]
WV = ['기온_평년차', '강수량_평년차', '일조_평년차', '고온일수_평년차', '영하일수_평년차']
w = w.sort_values(['계열키', '연월'])
for v in WV:
    g = w.groupby('계열키')[v]; w[v + '_3m'] = g.transform(lambda s: s.rolling(3, min_periods=2).mean()); w[v + '_12m'] = g.transform(lambda s: s.rolling(12, min_periods=9).mean())
WC = [v + s for v in WV for s in ('_3m', '_12m')]
w['mi'] = pd.PeriodIndex(w.연월, freq='M').year * 12 + pd.PeriodIndex(w.연월, freq='M').month - 1
pr = pd.read_csv(P84 + '02_계열_월별_생산피처_628.csv.gz' if FEAT in ('ext84', 'sig') else P26 + '04_변수_생산/02_계열_월별_사용가능_생산피처.csv.gz'); pr = pr[pr.계열키.isin(K)]
pr['mi'] = pd.PeriodIndex(pr.연월, freq='M').year * 12 + pr.연월.str[5:7].astype(int) - 1
PC = ['생산_면적_전년비_%', '생산_생산량_전년비_%', '면적매달_전년비_%']
X = w[['계열키', 'mi'] + WC].merge(pr[['계열키', 'mi'] + PC], on=['계열키', 'mi'], how='outer')
# 줄 만들기: 기준월 t (2018-12~), h 1..12
def sl(a, i, lo, hi):   # a[:, lo..hi] 합 (빈칸 무시, 다 비면 nan)
    lo = max(lo, 0); hi = min(hi, a.shape[1] - 1)
    if hi < lo: return np.full(a.shape[0] if a.ndim == 2 else 1, np.nan)
    x = a[i, lo:hi + 1] if np.ndim(i) == 0 else a[i][:, lo:hi + 1]
    return np.where(np.all(np.isnan(x), axis=-1), np.nan, np.nansum(x, axis=-1))
rows = []
for t in range(11, n):       # 2018-12부터
    for h in range(1, 13):
        m = t + h
        if m >= n + 12: continue
        r = pd.DataFrame({'kid': np.arange(len(K)), 't': t + T0, 'h': h, 'm': m + T0})
        r['목표달'] = (m + T0) % 12 + 1
        r['ly_q'] = Q[:, m - 12] if m - 12 < n else np.nan
        r['ly2_q'] = Q[:, m - 24] if 0 <= m - 24 < n else np.nan
        s12 = sl(qraw, slice(None), t - 11, t); s12p = sl(qraw, slice(None), t - 23, t - 12)
        s3 = sl(qraw, slice(None), t - 2, t); s3p = sl(qraw, slice(None), t - 14, t - 12)
        r['규모'] = np.log1p(s12); r['품종_12m변화'] = np.log1p(s12) - np.log1p(s12p); r['품종_3m변화'] = np.log1p(s3) - np.log1p(s3p)
        r['목표달비중'] = np.expm1(r.ly_q) / np.where(s12 > 0, s12, np.nan)
        ii = np.array([iid[i] for i in itm])
        i12 = IQ[:, max(t - 11, 0):t + 1].sum(1); i12p = IQ[:, max(t - 23, 0):max(t - 11, 0)].sum(1) if t >= 23 else np.full(len(items), np.nan)
        i3 = IQ[:, t - 2:t + 1].sum(1); i3p = IQ[:, t - 14:t - 11].sum(1) if t >= 14 else np.full(len(items), np.nan)
        r['품목_12m변화'] = (np.log1p(i12) - np.log1p(i12p))[ii]; r['품목_3m변화'] = (np.log1p(i3) - np.log1p(i3p))[ii]
        im12 = np.nansum(IM[:, max(t - 11, 0):t + 1], 1); im12p = np.nansum(IM[:, max(t - 23, 0):max(t - 11, 0)], 1) if t >= 23 else np.full(len(items), np.nan)
        ok = np.all(~np.isnan(IM[:, max(t - 23, 0):t + 1]), 1)
        r['수입_12m변화'] = np.where(ok, np.log1p(im12) - np.log1p(im12p), np.nan)[ii]
        r['y_q'] = (Q[:, m] if m < n else np.nan) - r.ly_q
        r['lp'] = PR[:, m] if m < n else np.nan; r['ly_lp'] = PR[:, m - 12] if m - 12 < n else np.nan
        rows.append(r)
D = pd.concat(rows, ignore_index=True)
D['계열키'] = K[D.kid]; D['품목코드'] = pd.Categorical(itm[D.kid]); D = D.merge(X.rename(columns={'mi': 't'}), on=['계열키', 't'], how='left')
D['목표sin'] = np.sin(2 * np.pi * D.목표달 / 12); D['목표cos'] = np.cos(2 * np.pi * D.목표달 / 12)
F = ['h', '목표달', '목표sin', '목표cos', '품목코드', '규모', 'ly_q', 'ly2_q', '목표달비중', '품종_12m변화', '품종_3m변화', '품목_12m변화', '품목_3m변화', '수입_12m변화'] + WC + PC
assert not any(c in F for c in ('lp', 'ly_lp')), '가격 입력 금지'

D['목표sin'] = np.sin(2 * np.pi * D.목표달 / 12); D['목표cos'] = np.cos(2 * np.pi * D.목표달 / 12)
F = ['h', '목표달', '목표sin', '목표cos', '품목코드', '규모', 'ly_q', 'ly2_q', '목표달비중', '품종_12m변화', '품종_3m변화', '품목_12m변화', '품목_3m변화', '수입_12m변화'] + WC + PC
if FEAT in ('drop', 'dropsig', 'dropsig86', 'dropsigH', 'dropsigN', 'dropsigW', 'dropsigD', 'dropsigD2', 'dropsigDI', 'dropsigDI2', 'dropsigD3', 'dropsigV', 'dropsigY', 'dropsigC', 'dropsig97', 'dropsig97S', 'dropsigS', 'dropsig97E', 'dropsig97EB', 'dropsig97EBS'): F = [c for c in F if c != '수입_12m변화' and c not in WC]
if FEAT in ('sig', 'dropsig', 'dropsig86', 'dropsigH', 'dropsigN', 'dropsigW', 'dropsigD', 'dropsigD2', 'dropsigDI', 'dropsigDI2', 'dropsigD3', 'dropsigV', 'dropsigY', 'dropsigC', 'dropsig97', 'dropsig97S', 'dropsigS', 'dropsig97E', 'dropsig97EB', 'dropsig97EBS'):
    S83 = pd.read_csv(P83 + '01_계열_기준월_목표월_월보신호.csv.gz', usecols=['계열키', '기준월', 'h', '신호_log'])
    S83['t'] = S83.기준월.str[:4].astype(int) * 12 + S83.기준월.str[5:7].astype(int) - 1
    D = D.merge(S83[['계열키', 't', 'h', '신호_log']].rename(columns={'신호_log': '월보신호'}), on=['계열키', 't', 'h'], how='left'); F = F + ['월보신호']
if FEAT == 'dropsig86':   # 86번 네이버 쇼핑인사이트 품종 클릭: 기준월까지 3달 평균의 전년 같은 3달 대비 log, 12달 평균 대비
    S86 = pd.read_csv(R + '00_기본자료/02_전처리/86_네이버쇼핑인사이트_품종클릭/01_품종_월_쇼핑클릭.csv'); S86 = S86[S86.계열키.isin(K)]
    S86['mi'] = S86.연월.str[:4].astype(int) * 12 + S86.연월.str[5:7].astype(int) - 1
    CK = np.full((len(K), n), np.nan)
    for k_, g_ in S86.groupby('계열키'):
        x_ = g_.groupby('mi').클릭_기준어대비.mean(); x_ = x_[(x_.index >= T0) & (x_.index <= T1)]; CK[kid[k_], x_.index - T0] = x_.values
    def win(a, lo, hi):
        lo = max(lo, 0); hi = min(hi, a.shape[1] - 1)
        return np.full(a.shape[0], np.nan) if hi < lo else np.nanmean(a[:, lo:hi + 1], axis=1)
    rows_ = []
    for t_ in range(n):
        c3 = win(CK, t_ - 2, t_); c3l = win(CK, t_ - 14, t_ - 12); c12 = win(CK, t_ - 11, t_)
        rows_.append(pd.DataFrame({'kid': np.arange(len(K)), 't': t_ + T0, '쇼핑클릭_전년비': np.log((c3 + 1e-9) / (c3l + 1e-9)), '쇼핑클릭_12달대비': np.log((c3 + 1e-9) / (c12 + 1e-9))}))
    X86 = pd.concat(rows_); X86 = X86.replace([np.inf, -np.inf], np.nan)
    D = D.merge(X86, on=['kid', 't'], how='left'); F = F + ['쇼핑클릭_전년비', '쇼핑클릭_12달대비']
    print('쇼핑클릭 값 있는 줄 %', round(D['쇼핑클릭_전년비'].notna().mean() * 100, 1), '| 계열', D.loc[D['쇼핑클릭_전년비'].notna(), '계열키'].nunique(), flush=True)
if FEAT == 'dropsigN':   # w44: 90번 위성 NDVI 산지 가중 평년차(기준월 t 값, 3달 평균)
    N9 = pd.read_csv(R + '00_기본자료/02_전처리/90_위성NDVI_품종산지/01_계열_월별_NDVI_628.csv.gz')
    N9['t'] = N9.연월.str[:4].astype(int) * 12 + N9.연월.str[5:7].astype(int) - 1
    D = D.merge(N9[['계열키', 't', 'NDVI_평년차', 'NDVI_평년차_3달']], on=['계열키', 't'], how='left'); F = F + ['NDVI_평년차', 'NDVI_평년차_3달']
    print('NDVI 값 있는 줄 %', round(D.NDVI_평년차.notna().mean() * 100, 1), flush=True)
if FEAT == 'dropsigW':   # w44: 89번 세계은행 원가(원유·요소·DAP·천연가스) 12달 로그 변화, 사용가능월(다음 달) 기준
    WB = pd.read_csv(R + '00_기본자료/02_전처리/89_운임KCCI_친환경GAP인증_품종/05b_세계은행_농산원가_관련_월별.csv')
    WB = WB[WB.상품.isin(['Crude oil, average', 'Urea', 'DAP', 'Natural gas index'])].pivot_table(index='사용가능월', columns='상품', values='값')
    WB.index = pd.PeriodIndex(WB.index, freq='M'); WB = WB.sort_index(); WC12 = np.log(WB / WB.shift(12)); WC12.columns = ['세계은행_' + c.split(',')[0].replace(' ', '') + '_12m' for c in WC12.columns]
    WC12['t'] = WC12.index.year * 12 + WC12.index.month - 1
    D = D.merge(WC12, on='t', how='left'); F = F + [c for c in WC12.columns if c != 't']
    print('세계은행 변수', [c for c in WC12.columns if c != 't'], flush=True)
if FEAT == 'dropsigH':   # w36: 명절 달력(77번과 같은 4개) — 목표달 기준, 설·추석 양력 날짜(음력 계산)
    from korean_lunar_calendar import KoreanLunarCalendar
    c_ = KoreanLunarCalendar(); SE, CH = {}, {}
    for y_ in range(2014, 2029):
        c_.setLunarDate(y_, 1, 1, False); SE[y_] = pd.Timestamp(c_.SolarIsoFormat()); c_.setLunarDate(y_, 8, 15, False); CH[y_] = pd.Timestamp(c_.SolarIsoFormat())
    mm_ = pd.PeriodIndex(year=D.m // 12, month=D.m % 12 + 1, freq='M') if hasattr(pd.PeriodIndex, 'from_fields') is False else pd.PeriodIndex.from_fields(year=D.m // 12, month=D.m % 12 + 1, freq='M')
    yy_ = (D.m // 12).values; d1_ = mm_.to_timestamp()
    D['H_설_목표월'] = [int(SE[y].to_period('M') == p) for y, p in zip(yy_, mm_)]; D['H_추석_목표월'] = [int(CH[y].to_period('M') == p) for y, p in zip(yy_, mm_)]
    D['H_추석까지일'] = [(CH[y] - d).days for y, d in zip(yy_, d1_)]; D['H_설까지일'] = [(SE[y] - d).days for y, d in zip(yy_, d1_)]
    F = F + ['H_설_목표월', 'H_추석_목표월', 'H_추석까지일', 'H_설까지일']
    print('추석 목표달 줄', int(D.H_추석_목표월.sum()), '| 2025 추석', CH[2025].date(), '2026', CH[2026].date(), flush=True)
if FEAT == 'dropsigD':   # w45: 92번 수요 추세 — 전국 인구 12달 변화(다음 달 사용), 품종 관심 몫(검색) 수준·24달 변화·검색 12달 변화, 품목 1인당 물량 3년 추세
    P92 = R + '00_기본자료/02_전처리/92_수요추세_인구_품종관심/'
    pp = pd.read_csv(P92 + '01_전국총인구_월별.csv'); pi_ = pd.PeriodIndex(pp.사용가능월, freq='M'); pp['t'] = pi_.year * 12 + pi_.month - 1
    D = D.merge(pp[['t', '총인구_12달log변화']].rename(columns={'총인구_12달log변화': 'D_인구_12달변화'}), on='t', how='left')
    vv = pd.read_csv(P92 + '02_계열_월별_품종관심추세.csv.gz'); pv_ = pd.PeriodIndex(vv.연월, freq='M'); vv['t'] = pv_.year * 12 + pv_.month - 1
    vv = vv.rename(columns={'품종관심비_12달log': 'D_품종관심비', '품종관심비_24달변화': 'D_품종관심_24달변화', '품종검색_12달log변화': 'D_품종검색_12달변화'})
    D = D.merge(vv[['계열키', 't', 'D_품종관심비', 'D_품종관심_24달변화', 'D_품종검색_12달변화']], on=['계열키', 't'], how='left')
    pm_ = pd.PeriodIndex(pp.연월, freq='M'); popm = pd.Series(pp.총인구.values, index=pm_.year * 12 + pm_.month - 1)
    IQn = np.where(np.isnan(IQ), 0, IQ); cs = np.cumsum(IQn, axis=1); cnt = np.cumsum(IQn > 0, axis=1)
    def s12(j, c):   # 열 c 까지 12달 합 (c-11..c), 9달 이상 물량 있을 때만
        if c < 11 or c >= n: return np.nan
        tot = cs[j, c] - (cs[j, c - 12] if c >= 12 else 0); k_ = cnt[j, c] - (cnt[j, c - 12] if c >= 12 else 0)
        return tot if k_ >= 9 and tot > 0 else np.nan
    u = D[['kid', 't']].drop_duplicates().copy(); vals = []
    for k_, tt in zip(u.kid.values, u.t.values):
        j = iid[itm[k_]]; c = tt - T0; a_ = s12(j, c); b_ = s12(j, c - 36); pa = popm.get(tt - 1, np.nan); pb = popm.get(tt - 37, np.nan)   # 인구는 한 달 늦게 앎
        vals.append((np.log(a_ / pa) - np.log(b_ / pb)) / 3 if np.isfinite([a_, b_, pa, pb]).all() else np.nan)
    u['D_품목1인당물량_3년추세'] = vals; D = D.merge(u, on=['kid', 't'], how='left')
    F = F + ['D_인구_12달변화', 'D_품종관심비', 'D_품종관심_24달변화', 'D_품종검색_12달변화', 'D_품목1인당물량_3년추세']
    for c_ in F[-5:]: print(c_, '값 있는 줄 %', round(D[c_].notna().mean() * 100, 1), flush=True)
if FEAT in ('dropsigD2', 'dropsigDI', 'dropsigDI2', 'dropsigD3', 'dropsigV', 'dropsigY'):   # w45: 수요 추세(공급 물량 빼고) / 수요 지수(과거 가격 예외 허용, 11-03 사용자 승인)
    P92 = R + '00_기본자료/02_전처리/92_수요추세_인구_품종관심/'
    if FEAT in ('dropsigD2', 'dropsigDI2', 'dropsigD3', 'dropsigV'):
        pp = pd.read_csv(P92 + '01_전국총인구_월별.csv'); pi_ = pd.PeriodIndex(pp.사용가능월, freq='M'); pp['t'] = pi_.year * 12 + pi_.month - 1
        D = D.merge(pp[['t', '총인구_12달log변화']].rename(columns={'총인구_12달log변화': 'D_인구_12달변화'}), on='t', how='left')
        vv = pd.read_csv(P92 + '02_계열_월별_품종관심추세.csv.gz'); pv_ = pd.PeriodIndex(vv.연월, freq='M'); vv['t'] = pv_.year * 12 + pv_.month - 1
        vv = vv.rename(columns={'품종관심비_12달log': 'D_품종관심비', '품종관심비_24달변화': 'D_품종관심_24달변화', '품종검색_12달log변화': 'D_품종검색_12달변화'})
        D = D.merge(vv[['계열키', 't', 'D_품종관심비', 'D_품종관심_24달변화', 'D_품종검색_12달변화']], on=['계열키', 't'], how='left')
        F = F + (['D_인구_12달변화'] if FEAT != 'dropsigV' else []) + ['D_품종관심비', 'D_품종관심_24달변화', 'D_품종검색_12달변화']
    if FEAT == 'dropsigY':   # w45d 가짜 비교(placebo): 기준월의 연도 숫자 하나만 — 인구 같은 '전국 한 값' 변수가 연도 추세 역할만 하는지 확인
        D['Y_연도'] = D.t // 12 + (D.t % 12) / 12; F = F + ['Y_연도']
    if FEAT == 'dropsigD3':   # w45c: 인구 구조 — 1인가구 비율(장래가구추계, 기준월 해 값)·5년 변화, 65세 이상 비율(연앙, 다음 해 7월부터 앎)·5년 변화
        h1 = pd.read_csv(P92 + '03_1인가구비율_연.csv'); D['_y'] = D.t // 12
        D = D.merge(h1[['연도', '1인가구비율', '1인가구비율_5년변화']].rename(columns={'연도': '_y', '1인가구비율': 'D_1인가구비율', '1인가구비율_5년변화': 'D_1인가구_5년변화'}), on='_y', how='left')
        g4 = pd.read_csv(P92 + '04_고령비율_연.csv'); g4['ua'] = g4.사용가능월.str[:4].astype(int) * 12 + g4.사용가능월.str[5:7].astype(int) - 1; g4 = g4.sort_values('ua')
        tt_ = pd.DataFrame({'t': np.sort(D.t.unique())})
        tt_ = pd.merge_asof(tt_, g4[['ua', '65세이상비율', '65세이상_5년변화']].rename(columns={'ua': 't', '65세이상비율': 'D_고령비율', '65세이상_5년변화': 'D_고령_5년변화'}), on='t', direction='backward')
        D = D.merge(tt_, on='t', how='left').drop(columns='_y'); F = F + ['D_1인가구비율', 'D_1인가구_5년변화', 'D_고령비율', 'D_고령_5년변화']
        print('인구구조 2025-01 기준월:', D.loc[D.t == 2025 * 12, ['D_1인가구비율', 'D_고령비율']].iloc[0].round(4).to_dict(), flush=True)
    if FEAT in ('dropsigDI', 'dropsigDI2'):
        # 수요 지수 (고정식): 품목 역수요 ln P = a − f·ln Q + d  →  d 의 12달 변화 = Δ12 ln P + f·Δ12 ln Q
        #  P = 품목 물량가중 단가(대상 품종 합), Q = 품목 물량. f 는 2022-12 까지 자료로 품목마다 한 번 고정(OLS Δ12lnP ~ Δ12lnQ, 기울기 부호 바꿈, [0.1, 3] 자름, 24점 미만이면 전체 중앙값)
        #  기준월 t 까지 값만 씀(가격·물량 모두 t 에 앎). 실제 수요량이 아니라 '수요 지수'
        Pr = np.exp(PR); num_ = np.vstack([np.nansum(np.where(np.isnan(qraw[itm == i]) | np.isnan(Pr[itm == i]), 0, qraw[itm == i] * Pr[itm == i]), axis=0) for i in items])
        den_ = np.vstack([np.nansum(np.where(np.isnan(qraw[itm == i]) | np.isnan(Pr[itm == i]), 0, qraw[itm == i]), axis=0) for i in items])
        ILP = np.where(den_ > 0, np.log(np.where(den_ > 0, num_ / np.where(den_ > 0, den_, 1), np.nan)), np.nan); ILQ = np.where(IQ > 0, np.log(np.where(IQ > 0, IQ, 1)), np.nan)
        dP = np.full_like(ILP, np.nan); dQ = np.full_like(ILQ, np.nan); dP[:, 12:] = ILP[:, 12:] - ILP[:, :-12]; dQ[:, 12:] = ILQ[:, 12:] - ILQ[:, :-12]
        cut = 2022 * 12 + 11 - T0; fv = np.full(len(items), np.nan)
        for j in range(len(items)):
            a_, b_ = dQ[j, :cut + 1], dP[j, :cut + 1]; ok = np.isfinite(a_) & np.isfinite(b_) & (np.abs(a_) < 3) & (np.abs(b_) < 3)
            if ok.sum() >= 24 and np.var(a_[ok]) > 1e-6: fv[j] = np.clip(-np.cov(a_[ok], b_[ok])[0, 1] / np.var(a_[ok], ddof=1), 0.1, 3)
        fmed = np.nanmedian(fv); fv = np.where(np.isnan(fv), fmed, fv)
        DI = dP + fv[:, None] * dQ
        DI3 = pd.DataFrame(DI.T).rolling(3, min_periods=2).mean().T.values; DI12 = pd.DataFrame(DI.T).rolling(12, min_periods=9).mean().T.values
        u = D[['kid', 't']].drop_duplicates().copy(); jj = np.array([iid[itm[k_]] for k_ in u.kid.values]); cc = u.t.values - T0
        u['DI_수요지수_3달'] = DI3[jj, cc]; u['DI_수요지수_12달'] = DI12[jj, cc]; D = D.merge(u, on=['kid', 't'], how='left')
        F = F + ['DI_수요지수_3달', 'DI_수요지수_12달']
        rows_ = []
        for j, i in enumerate(items):
            for c in range(n):
                if np.isfinite(DI[j, c]): rows_.append((i, c + T0, fv[j], dQ[j, c], dP[j, c], DI[j, c], DI3[j, c]))
        E = pd.DataFrame(rows_, columns=['품목코드4', 'mi', 'f_역탄력', 'dlnQ_12', 'dlnP_12', '수요지수', '수요지수_3달'])
        E['연월'] = [f'{m // 12}-{m % 12 + 1:02d}' for m in E.mi]; E.drop(columns='mi').to_csv(OUTD / '48b_수요지수_품목월.csv', index=False, encoding='utf-8-sig')
        print('수요지수: 품목', len(items), 'f 중앙', round(fmed, 3), 'f 직접추정 품목', int(np.isfinite(fv).sum()), '| 값 있는 줄 %', round(D.DI_수요지수_3달.notna().mean() * 100, 1), flush=True)
if FEAT in ('dropsigC', 'dropsig97', 'dropsig97S', 'dropsig97E', 'dropsig97EB', 'dropsig97EBS'):   # w46 (11-04): 92 기후지수·NMME 계절예측 / 97 농업주산지 품종 기상
    if FEAT == 'dropsigC':
        PC_ = R + '00_기본자료/02_전처리/92_기후지수_ENSO_AO_PDO_DMI/'
        cw = pd.read_csv(PC_ + '02_기후지수_월별_wide.csv'); pu_ = pd.PeriodIndex(cw.사용가능_연월, freq='M'); cw['ua'] = pu_.year * 12 + pu_.month - 1
        CC = ['NINO34_3달평균', 'AO_3달평균', 'PDO_3달평균', 'DMI_3달평균']
        cw = cw.dropna(subset=['NINO34_3달평균']).sort_values('ua')
        tt_ = pd.merge_asof(pd.DataFrame({'t': np.sort(D.t.unique())}), cw[['ua'] + CC].rename(columns={'ua': 't'}), on='t', direction='backward')   # 기준월 t 까지 나온 최신 지수
        D = D.merge(tt_.rename(columns={c: 'C_' + c for c in CC}), on='t', how='left')
        nm_ = pd.read_csv(PC_ + '03_NMME_계절예측_한반도.csv'); nm_ = nm_[(nm_.모델 == 'NCEP-CFSv2') & (nm_.구분 == 'FORECAST')].copy()
        pi_ = pd.PeriodIndex(nm_.발표월, freq='M'); nm_['t'] = pi_.year * 12 + pi_.month - 1; nm_['h'] = nm_.앞달
        # 온난화 치우침 빼기: 같은 앞달의 그 발표월 전 120달 평균을 뺌 (발표 시점에 아는 값만)
        nm_ = nm_.sort_values(['h', 't'])
        for c in ('기온_평년차', '강수_평년차_mm'):
            nm_[c + '_보정'] = nm_[c] - nm_.groupby('h')[c].transform(lambda s: s.shift(1).rolling(120, min_periods=36).mean())
        D = D.merge(nm_[['t', 'h', '기온_평년차_보정', '강수_평년차_mm_보정']].rename(columns={'기온_평년차_보정': 'C_NMME기온_목표달', '강수_평년차_mm_보정': 'C_NMME강수_목표달'}), on=['t', 'h'], how='left')
        F = F + ['C_' + c for c in CC] + ['C_NMME기온_목표달', 'C_NMME강수_목표달']
        print('기후 변수 값 있는 줄 %', {c: round(D[c].notna().mean() * 100, 1) for c in F[-6:]}, flush=True)
    if FEAT in ('dropsig97', 'dropsig97S', 'dropsig97E', 'dropsig97EB', 'dropsig97EBS'):
        g7 = pd.read_csv(R + '00_기본자료/02_전처리/97_농업주산지_품종기상/03_계열_월별_주산지기상_2015_2026.csv')
        pu_ = pd.PeriodIndex(g7.사용가능월, freq='M'); g7['t'] = pu_.year * 12 + pu_.month - 1; g7['달'] = pd.PeriodIndex(g7.연월, freq='M').month
        g7 = g7[g7.연월 < os.environ.get('NC_CUT', '2026-11')]   # 덜 찬 달은 뺌 (기본 2026-11: 2일치). 월 자동 실행은 NC_CUT = 기준월 다음 달
        base = g7[g7.연월 < '2023-01'].groupby(['계열키', '달'])[['평균기온', '강수합', '일조합']].mean().add_suffix('_평년')   # 평년 = 첫 시험 해 전(2015~2022)
        g7 = g7.join(base, on=['계열키', '달'])
        g7['W97_기온차'] = g7.평균기온 - g7.평균기온_평년; g7['W97_강수비'] = np.log((g7.강수합 + 10) / (g7.강수합_평년 + 10)); g7['W97_일조비'] = np.log((g7.일조합 + 10) / (g7.일조합_평년 + 10))
        g7 = g7.sort_values(['계열키', 't'])
        for c in ('W97_기온차', 'W97_강수비', 'W97_일조비', '고온일_33도', '특보일_전체'):
            g7[c + '_3달'] = g7.groupby('계열키')[c].transform(lambda s: s.rolling(3, min_periods=2).mean())
        W7 = ['W97_기온차', 'W97_기온차_3달', 'W97_강수비_3달', 'W97_일조비_3달', '고온일_33도_3달', '특보일_전체_3달']
        D = D.merge(g7[['계열키', 't'] + W7], on=['계열키', 't'], how='left'); F = F + W7
        print('97 기상 값 있는 줄 %', round(D.W97_기온차.notna().mean() * 100, 1), '| 계열', D.loc[D.W97_기온차.notna(), '계열키'].nunique(), flush=True)
if FEAT in ('dropsig97S', 'dropsigS', 'dropsig97EBS'):   # w52 (11-04): 99 산지공판장 품종 물량(공급) — 사용가능월(다음 달) 기준
    S9 = pd.read_csv(R + '00_기본자료/02_전처리/99_산지공판장_품종물량/02_계열_월별_산지물량변수.csv')
    pu_ = pd.PeriodIndex(S9.사용가능월, freq='M'); S9['t'] = pu_.year * 12 + pu_.month - 1
    S9C = ['산지_3m전년비', '산지_12m전년비', '산지_품목_3m전년비', '산지_비중_12m']
    D = D.merge(S9[['계열키', 't'] + S9C], on=['계열키', 't'], how='left'); F = F + S9C
    print('99 산지 값 있는 줄 %', round(D.산지_3m전년비.notna().mean() * 100, 1), '| 계열', D.loc[D.산지_3m전년비.notna(), '계열키'].nunique(), flush=True)
if FEAT in ('dropsig97E', 'dropsig97EB', 'dropsig97EBS'):   # u6 (11-05): 99 ERA5 재분석(품종 산지 가중) + 넓은 영역 해수온·기압 / 94 방재월보 극값. 사용가능월 = 연월 + 1
    UP_ = '/mnt/user-data/uploads/농산물 프로젝트/분석용/00_기본자료/02_전처리/'
    _rep = {}
    if (OUTD / 'u1_단위표.csv').exists():
        _t = pd.read_csv(OUTD / 'u1_단위표.csv'); _rep = dict(zip(_t.모델계열키, _t.대표품종키))
    D['_wkey'] = D.계열키.map(lambda k: _rep.get(k, k))
    def _attach(df, cols, pref):
        global D, F
        df = df.copy(); pu_ = pd.PeriodIndex(df.연월, freq='M') + 1; df['t'] = pu_.year * 12 + pu_.month - 1
        df = df[['계열키', 't'] + cols].rename(columns={'계열키': '_wkey', **{c: pref + c for c in cols}}).drop_duplicates(['_wkey', 't'])
        D = D.merge(df, on=['_wkey', 't'], how='left'); F = F + [pref + c for c in cols]
    e_ = pd.read_csv(UP_ + '99_ERA5_재분석_품종산지/02_계열_월별_ERA5_628.csv.gz')
    _attach(e_, ['기온_평년차', '강수_mm_평년차', '토양수분_평년차', '적설_cm_평년차', '기온_평년차_3달', '강수_mm_평년차_3달', '토양수분_평년차_3달'], 'E5_')
    o_ = pd.read_csv(UP_ + '99_ERA5_재분석_품종산지/03_넓은영역_해수온기압지수_월별.csv'); pu_ = pd.PeriodIndex(o_.연월, freq='M') + 1; o_['t'] = pu_.year * 12 + pu_.month - 1
    OC = ['한반도주변해_해수온_평년차', '북서태평양_해수온_평년차', 'Nino34_해수온_평년차', '시베리아고기압_해면기압_평년차', '북태평양고기압_해면기압_평년차']
    D = D.merge(o_[['t'] + OC].rename(columns={c: 'E5_' + c for c in OC}), on='t', how='left'); F = F + ['E5_' + c for c in OC]
    if FEAT in ('dropsig97EB', 'dropsig97EBS'):
        b_ = pd.read_csv(UP_ + '94_방재월보_지점극값_품종산지/03_계열_월별_방재월보_628.csv.gz')
        _attach(b_, ['최고기온_시도최대_평년차', '최저기온_시도최소_평년차', '1시간최다강수_시도최대_평년차', '월강수량_평년차'], 'B94_')
    print('ERA5 값 있는 줄 %', round(D.E5_기온_평년차.notna().mean() * 100, 1), '| 계열', D.loc[D.E5_기온_평년차.notna(), '계열키'].nunique(), flush=True)
    D = D.drop(columns='_wkey')
assert not any(c in F for c in ('lp', 'ly_lp')), '가격 직접 입력 금지(수요지수 DI_ 는 예외 승인 11-03)'
if os.environ.get('NC_NOQ') == '1':   # 11-12 팀 원칙: 도매시장 반입량(경매 물량) 변수 뺌 — 가격에 반응하는 양이라
    F = [c for c in F if c not in ('규모', 'ly_q', 'ly2_q', '목표달비중', '품종_12m변화', '품종_3m변화', '품목_12m변화', '품목_3m변화')]
print('변수 세트', FEAT, '변수 수', len(F), flush=True)
FN = [c for c in F if c != '품목코드']
def num(x, med):   # 선형·RF용: 빈칸 = 학습 중앙값 + 빈칸 표시
    z = x[FN].astype(float); m = z.isna().astype(float).add_suffix('_빈'); return pd.concat([z.fillna(med), m[[c + '_빈' for c in ('ly2_q', '수입_12m변화', WC[0], PC[0], PC[2])]]], axis=1)
def lgbr(tr, y, w=None, obj='l1'):
    return lgb.LGBMRegressor(n_estimators=400, learning_rate=0.03, num_leaves=15, min_child_samples=50, subsample=0.8, subsample_freq=1, colsample_bytree=0.7, objective=obj, random_state=0, verbose=-1).fit(tr[F], y, sample_weight=w)
out = []
for Y in (2023, 2024, 2025):
    t0 = time.time(); s0 = Y * 12; e0 = (Y + 1) * 12 if Y < 2025 else 10**9
    tr = D[(D.m < s0)].copy(); te = D[(D.m >= s0) & (D.m < e0)].copy()
    trp = P[P.mi < s0].dropna(subset=['lp']).assign(달=lambda x: x.mi % 12 + 1)
    S = trp.groupby(['kid', '달']).lp.mean(); Sk = trp.groupby('kid').lp.mean()
    for x in (tr, te): x['계절'] = [S.get((k, mm), np.nan) for k, mm in zip(x.kid, x.목표달)]; x['계절'] = x['계절'].fillna(x.kid.map(Sk))
    a = tr.dropna(subset=['y_q']); m_l = lgbr(a, a.y_q, np.sqrt(np.expm1(a.ly_q) + 1)); te['qd_LGB'] = m_l.predict(te[F])
    b = tr.dropna(subset=['lp', '계절']); p_l = lgbr(b, b.lp - b.계절); te['pd_LGB'] = p_l.predict(te[F])
    te['시험'] = f'{Y}' if Y < 2025 else '2025~'; out.append(te[['계열키', 'kid', 't', 'h', 'm', 'ly_q', 'y_q', 'lp', '계절', 'qd_LGB', 'pd_LGB', '시험']])
    print(Y, '학습', len(tr), '시험', len(te), round(time.time() - t0), '초', flush=True)
O = pd.concat(out); O.to_pickle(OUTD / f'_w23_{FEAT}.pkl')

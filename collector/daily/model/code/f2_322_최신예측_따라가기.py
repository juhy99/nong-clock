# -*- coding: utf-8 -*-
"""f2 (11-11) 322단위 최종 예측: v4(C2, tV 계열) + 품목 따라가기(tW 부모 v4) + 반반, 단위마다 정한 모델(e10 F2 규칙), 출하철 달만
 입력: <tV폴더>/_final_C2_최신기준.pkl · _final_C2.pkl, <tW폴더>/같은 두 파일, 단위표(v3b 322), 단위별 모델·출하철(e10)
 따라가기(log): 단위 작년 같은 달 + (부모 v4 − 부모 작년 같은 달).  반반 = (v4 + 따라)/2.  구간은 v4 구간을 같은 비율로 옮김
 사용: python f2_322_최신예측_따라가기.py <tV폴더> <tW폴더> <단위표 csv> <e10 단위별 csv> <출력폴더>"""
import sys, os, numpy as np, pandas as pd
TV, TW, VF, EF, OUT = sys.argv[1:6]; os.makedirs(OUT, exist_ok=True)
V = pd.read_csv(VF); R = pd.read_csv(EF).set_index('예측단위'); F = 'F2 +품목 따라가기'
M4 = {'만감 레드향': '감귤 레드향', '만감 황금향': '감귤 황금향', '만감 카라향': '감귤 카라향', '만감 천혜향': '감귤 천혜향'}   # 감귤·만감 코드 합침: 가격은 물량 큰 감귤 쪽 계열
UV = pd.read_csv(TV + '/u1_단위표.csv').set_index('예측단위').모델계열키
UW = pd.read_csv(TW + '/u1_단위표.csv'); PAR = UW[UW.묶음 == '품목(합침)'].set_index('품목명')
ym = lambda mi: f'{mi // 12}-{mi % 12 + 1:02d}'
def prep(df):
    df = df.copy(); df['목표월'] = df.m.map(ym); df['기준월'] = df.t.map(ym); return df
# ---- 최신 기준월 앞으로 12달
fV = prep(pd.read_pickle(TV + '/_final_C2_최신기준.pkl')).set_index(['계열키', 'h']); fW = prep(pd.read_pickle(TW + '/_final_C2_최신기준.pkl')).set_index(['계열키', 'h'])
rows = []
for v in V.itertuples():
    un = v.예측단위; src = un if un in UV.index and not UV[un] is None and un in M4 and UV[un].startswith('0615') else M4.get(un, un); key = UV[src]; r = R.loc[un]; mdl = r[f'{F}|모델']; ss = set(map(int, str(r.출하철).split(',')))
    pk = PAR.모델계열키.get(v.품목명) if v.품목명 in PAR.index else None
    for h in range(1, 13):
        a = fV.loc[(key, h)]; p, lo, hi = a.f_섞기, a.f_섞기 + a.q10, a.f_섞기 + a.q90; ly = a.ly_lp; fol = np.nan
        if pk is not None and (pk, h) in fW.index:
            b = fW.loc[(pk, h)]; fol = ly + (b.f_섞기 - b.ly_lp)
        use = p
        if mdl != 'v4' and np.isfinite(fol): use = fol if mdl == '따라' else (p + fol) / 2
        k = use - p
        rows.append(dict(예측단위=un, 품목=v.품목명, 묶음=v.묶음, 모델계열키=key, 부모계열키=pk, 모델=mdl, 기준월=a.기준월, 목표월=a.목표월, h=h,
                         출하철=int(int(a.목표월[5:]) in ss), 예측_원kg=np.exp(use), 하한10=np.exp(lo + k), 상한90=np.exp(hi + k), 작년같은달_원kg=np.exp(ly),
                         v4_원kg=np.exp(p), 따라가기_원kg=np.exp(fol), 평균판_원kg=np.exp(a.f_평균판), 작년반반_원kg=np.exp(a.f_작년반반), 섞기판_원kg=np.exp(a.f_섞기_w47), v4_상황판식_원kg=np.exp(a.f_C2_상황판식),
                         월보adj=a.월보adj, 등급_2023_24=r[f'{F}|등급']))
FC = pd.DataFrame(rows); FC.loc[FC.출하철 == 0, ['예측_원kg', '하한10', '상한90']] = np.nan
FC.round(4).to_csv(OUT + '/01_322_앞으로12달_예측.csv', index=False, encoding='utf-8-sig')
print('앞으로 예측 기준월', FC.기준월.iloc[0], '| 단위', FC.예측단위.nunique(), '| 줄', len(FC), '| 출하철 예측 줄', int(FC.예측_원kg.notna().sum()), '| 모델', FC.drop_duplicates('예측단위').모델.value_counts().to_dict(), flush=True)
# ---- 시험 기간(2023-01~) 같은 규칙으로 다시: 단위 예측 vs 실제
oV = prep(pd.read_pickle(TV + '/_final_C2.pkl')).drop_duplicates(['계열키', 't', 'h']).set_index(['계열키', 't', 'h'])
oW = prep(pd.read_pickle(TW + '/_final_C2.pkl')).drop_duplicates(['계열키', 't', 'h']).set_index(['계열키', 't', 'h'])
T = []
for v in V.itertuples():
    un = v.예측단위; src = un if un in UV.index and not UV[un] is None and un in M4 and UV[un].startswith('0615') else M4.get(un, un); key = UV[src]; r = R.loc[un]; mdl = r[f'{F}|모델']; ss = set(map(int, str(r.출하철).split(',')))
    a = oV.loc[key].copy(); pk = PAR.모델계열키.get(v.품목명) if v.품목명 in PAR.index else None
    a['따라'] = np.nan
    if pk is not None:
        b = oW.loc[pk]; j = b.reindex(a.index); a['따라'] = a.ly_lp + (j.f_섞기 - j.ly_lp)
    a['최종'] = a.f_섞기 if mdl == 'v4' else np.where(a.따라.notna(), a.따라 if mdl == '따라' else (a.f_섞기 + a.따라) / 2, a.f_섞기)
    a = a.reset_index(); a['예측단위'] = un; a['모델'] = mdl; a['출하철'] = a.목표월.str[5:].astype(int).isin(ss).astype(int); T.append(a)
T = pd.concat(T); T = T.assign(예측_원kg=np.exp(T.최종), 실제_원kg=np.exp(T.lp), 작년같은달_원kg=np.exp(T.ly_lp), v4_원kg=np.exp(T.f_섞기), 따라가기_원kg=np.exp(T.따라))
cols = ['예측단위', '모델', '기준월', '목표월', 'h', '출하철', '예측_원kg', '실제_원kg', '작년같은달_원kg', 'v4_원kg', '따라가기_원kg', '시험']
T[cols].round(2).to_csv(OUT + '/02_322_시험예측_2023부터.csv.gz', index=False, compression='gzip')
L = T[(T.출하철 == 1)].dropna(subset=['예측_원kg', '실제_원kg', '작년같은달_원kg']).copy()
L['e'] = (L.예측_원kg / L.실제_원kg - 1).abs() * 100; L['e0'] = (L.작년같은달_원kg / L.실제_원kg - 1).abs() * 100
L['구간'] = np.select([L.목표월 < '2025-01', L.목표월 < '2026-01', L.목표월 < '2026-06', L.목표월 < '2026-09', L.목표월 < '2026-10'],
                    ['① 2023~24', '② 2025', '③ 2026.01~05', '③b 2026.06~08(새로 채운 달)', '③ 2026.09'], '④ 2026.10')
S = []
for g, x in L.groupby('구간'):
    u = x.groupby('예측단위')[['e', 'e0']].mean(); S.append((g, len(u), round(100 - u.e.median(), 1), round(100 - u.e0.median(), 1)))
S = pd.DataFrame(S, columns=['구간', '단위', '우리', '작년그대로']); print(S.to_string(index=False)); S.to_csv(OUT + '/03_시험_성적.csv', index=False, encoding='utf-8-sig')

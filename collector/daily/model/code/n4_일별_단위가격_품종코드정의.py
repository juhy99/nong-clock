# -*- coding: utf-8 -*-
"""n4 (11-12) 원장 일별(품목코드×품종코드) → 322단위 일별 국산 단가, 새 정의(DB 정의 − 손질·형태·수입 표시·통일알타리) 그대로
 단위 = 정의 코드 합, 그 단위 달만. 하루 국산 100kg 미만이면 단가 비움, 단위 오류 날(앞뒤 30일 중앙의 1/8 미만 & 물량 8배 초과) 비움 (u7과 같음)
 사용: python n4_일별_단위가격_품종코드정의.py <새정의 csv> <출력 csv.gz> <일별 품종코드 csv.gz> [<더 붙일 일별 csv> ...]"""
import sys, numpy as np, pandas as pd
DEF, OUT, *SRC = sys.argv[1:]
N = pd.read_csv(DEF, dtype=str); N['달'] = N.달.fillna(','.join(map(str, range(1, 13))))   # 빈칸 = 1~12월
d = pd.concat([pd.read_csv(f, dtype={'일자': str, '품목코드4': str, '품종코드': str}) for f in SRC])
d['c4'] = d.품목코드4.str.zfill(4); d['vc'] = d.품종코드.str.zfill(2); d = d.drop_duplicates(['일자', 'c4', 'vc'], keep='last')
d['date'] = pd.to_datetime(d.일자, format='%Y%m%d'); d['mo'] = d.date.dt.month
rows = []
for u, g in N.groupby('단위', sort=False):
    mm = set(map(int, g.달.iloc[0].split(','))); s = set(zip(g.c4, g.vc))
    x = d[pd.Series(list(zip(d.c4, d.vc)), index=d.index).isin(s) & d.mo.isin(mm)].groupby('date')[['국산_kg', '국산금액_원']].sum()
    rows.append(x.reset_index().assign(단위=u, 품목=g.품목.iloc[0] if '품목' in g else '', 묶음=g.묶음.iloc[0] if '묶음' in g else ''))
A = pd.concat(rows); A['p'] = np.where(A.국산_kg >= 100, A.국산금액_원 / A.국산_kg, np.nan); A = A.sort_values(['단위', 'date'])
def fixu(g):
    p = g.p; q = g.국산_kg; mp = p.rolling(61, center=True, min_periods=10).median(); mq = q.rolling(61, center=True, min_periods=10).median()
    return p.where(~((p < mp / 8) & (q > mq * 8)))
A['p'] = A.groupby('단위', group_keys=False).apply(fixu)
A.to_csv(OUT, index=False, compression='gzip'); print('단위', A.단위.nunique(), '줄', len(A), A.date.min().date(), '~', A.date.max().date(), '| 단가 있는 줄', int(A.p.notna().sum()))

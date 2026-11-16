# -*- coding: utf-8 -*-
"""p104b (11-13) p104a + 거래 줄 단위 오류 빼기 (팀 DB와 같은 규칙)
 같은 달·같은 품목코드·품종코드 거래 줄 안에서, 줄 단가(총금액 ÷ 총물량)가 줄 수 기준 중앙 단가의 1/8 미만이면서
 줄 물량이 줄 물량 중앙의 8배를 넘는 줄은 뺌 (물량 단위를 잘못 적은 거래)
 나머지 규칙은 p104a와 같음: 상위 50품목, 단위코드 12(kg), 물량·금액 > 0, 국산/수입 = 산지명(parse_san)
 사용: python p104b.py <월별CSV> <중간폴더> <build_sanji_weather 폴더> <상위품목코드 csv> [초제한=160]"""
import glob, os, sys, time, numpy as np, pandas as pd
src, out, sj, topf = sys.argv[1:5]; lim = float(sys.argv[5]) if len(sys.argv) > 5 else 160
sys.path.insert(0, sj); from build_sanji_weather import parse_san
TOP = set(pd.read_csv(topf, dtype=str).품목코드4); t0 = time.time(); cache = {}
cols = ['정산일자', '대분류코드', '중분류코드', '소분류코드', '단위코드', '산지명', '총물량', '총금액']
for f in sorted(glob.glob(os.path.join(src, '*.csv'))):
    ym = os.path.basename(f)[:6]; o = os.path.join(out, f'd_{ym}.csv')
    if os.path.exists(o): continue
    if time.time() - t0 > lim: break
    parts = []
    for d in pd.read_csv(f, usecols=cols, dtype=str, encoding='utf-8-sig', keep_default_na=False, chunksize=500000):
        d = d[d.단위코드 == '12']; d['품목코드4'] = d.대분류코드.str.zfill(2) + d.중분류코드.str.zfill(2); d = d[d.품목코드4.isin(TOP)]
        d = d.assign(q=pd.to_numeric(d.총물량, errors='coerce'), a=pd.to_numeric(d.총금액, errors='coerce')); d = d[(d.q > 0) & (d.a > 0)]
        parts.append(d)
    d = pd.concat(parts); d['품종코드'] = d.소분류코드.str.zfill(2); d['up'] = d.a / d.q
    g = d.groupby(['품목코드4', '품종코드']); mp = g.up.transform('median'); mq = g.q.transform('median')
    bad = (d.up < mp / 8) & (d.q > mq * 8); nb, qb = int(bad.sum()), float(d.q[bad].sum()); qt = float(d.q.sum()); d = d[~bad]
    s = d.산지명.str.strip()
    for u in s.unique():
        if u not in cache:
            badn = any(k in u for k in ('시장', '농수산', '공판장', '도매')) or u in ('서울특별시', '서울', '')
            cache[u] = '미상' if badn else (parse_san(u)[0] or '미상')
    dom = s.map(cache) == '국산'; d['qd'] = d.q.where(dom, 0.0); d['ad'] = d.a.where(dom, 0.0)
    r = d.groupby(['정산일자', '품목코드4', '품종코드'], as_index=False)[['q', 'a', 'qd', 'ad']].sum()
    r.columns = ['일자', '품목코드4', '품종코드', '물량_kg', '금액_원', '국산_kg', '국산금액_원']
    r.to_csv(o, index=False, encoding='utf-8')
    with open(os.path.join(out, '_뺀줄.csv'), 'a', encoding='utf-8') as fh: fh.write(f'{ym},{nb},{qb:.1f},{qt:.1f}\n')
    print(ym, '뺀 줄', nb, '물량 %', round(qb / qt * 100, 3), round(time.time() - t0), flush=True)
print('끝', round(time.time() - t0))

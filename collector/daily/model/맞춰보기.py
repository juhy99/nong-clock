# -*- coding: utf-8 -*-
"""월 예측(v4) 결과 두 개가 같은지 숫자로 비교 (2026-11-16)
  python 맞춰보기.py <기준 01_322_월예측_…csv> <내가 돌린 01_322_월예측_…csv>
줄 수 · 열 · (예측단위, 목표월) 열쇠 · 숫자 열마다 최대 차이를 보여 주고, 모두 0 이면 '같음'"""
import sys
import pandas as pd
a, b = (pd.read_csv(p, encoding='utf-8-sig') for p in sys.argv[1:3])
k = ['예측단위', '목표월']
print(f'줄 수 {len(a):,} vs {len(b):,} · 열 같음 {list(a.columns) == list(b.columns)}')
m = a.merge(b, on=k, how='outer', suffixes=('_a', '_b'), indicator=True)
print('열쇠가 한쪽에만 있는 줄:', int((m._merge != 'both').sum()))
m = m[m._merge == 'both']
num = [c for c in a.columns if c not in k and pd.api.types.is_numeric_dtype(a[c])]
worst = 0.0
for c in num:
    d = (m[c + '_a'] - m[c + '_b']).abs()
    r = (d / m[c + '_a'].abs()).replace([float('inf')], 0).fillna(0)
    worst = max(worst, float(r.max()))
    print(f'  {c:<20} 최대 차이 {d.max():.6g} (상대 {r.max() * 100:.6f}%) · 다른 줄 {(d > 1e-6).sum():,}')
txt = [c for c in a.columns if c not in k and c not in num]
for c in txt:
    print(f'  {c:<20} 글자 다른 줄 {(m[c + "_a"].fillna('').astype(str) != m[c + "_b"].fillna('').astype(str)).sum():,}')
print('결과:', '같음 (모든 숫자 차이 0)' if worst == 0 else f'다름 — 가장 큰 상대 차이 {worst * 100:.6f}%')

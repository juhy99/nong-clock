# -*- coding: utf-8 -*-
"""공급 변수(자료뿌리)를 새 기준월까지 이어 붙이기. 2026-11-13
 새 공표·새 월보가 아직 처리되지 않았을 때 모델이 빈칸으로 돌지 않게 하는 안전한 이어 붙이기:
  · 면적·생산 공표(26/04): 계열마다 마지막 달 값을 새 달로 그대로 (공표 값은 다음 공표 전까지 안 바뀜)
  · 월보 신호(83): 새 기준월의 (h) = 지난 기준월의 (h+1) — 같은 목표월, 같은 월보 호. h=12는 빈칸
  · 주산지 기상(97): 손대지 않음 (새 달 값은 collect_monthly.py juju → 97번 전처리로만 들어옴)
 새 공표·월보를 처리한 파일을 자료뿌리에 넣으면 그 값이 우선 (이미 있는 달은 건드리지 않음)
 사용: python feat_roll.py <자료뿌리 폴더> <기준월 YYYY-MM>"""
import sys, os, pandas as pd
R, BASE = sys.argv[1], sys.argv[2]
nxt = lambda m, k=1: str(pd.Period(m, freq='M') + k)
f = os.path.join(R, '26_품종구분_전처리_변수', '04_변수_생산', '02_계열_월별_사용가능_생산피처.csv.gz')
x = pd.read_csv(f, dtype=str, keep_default_na=False); last = x.연월.max(); add = []
m = last
while m < BASE:
    m = nxt(m); add.append(x[x.연월 == last].assign(연월=m))
if add: pd.concat([x] + add).to_csv(f, index=False, compression='gzip')
print(f'면적·생산 공표: {last} → {max(last, BASE)} ({len(add)}달 이어 붙임)')
f = os.path.join(R, '00_기본자료', '02_전처리', '83_품종_월보생산전망_신호', '01_계열_기준월_목표월_월보신호.csv.gz')
x = pd.read_csv(f); last = x.기준월.max(); n = 0
while x.기준월.max() < BASE:
    prev = x.기준월.max(); b = nxt(prev); y = x[(x.기준월 == prev) & (x.h >= 2)].copy(); y['기준월'] = b; y['h'] = y.h - 1
    x = pd.concat([x, y], ignore_index=True); n += 1
if n: x.to_csv(f, index=False, compression='gzip')
print(f'월보 신호: {last} → {x.기준월.max()} ({n}달 이어 붙임, 새 월보 호는 반영 안 됨)')
f = os.path.join(R, '00_기본자료', '02_전처리', '97_농업주산지_품종기상', '03_계열_월별_주산지기상_2015_2026.csv')
print('주산지 기상(97) 마지막 달:', pd.read_csv(f, usecols=['연월']).연월.max(), '(그대로)')

# -*- coding: utf-8 -*-
"""f1 (11-11) 최종 v4(C2)를 새 패널로 다시 돌림: w47을 그대로 실행 → 시험 예측(2023/2024/2025~) + 최신 기준월 1~12달
 C2(v4) = log 평균(섞기, 작년반반, 평균판) — 시험 성적과 같은 식. 최신 기준월 줄도 세 판을 모두 저장
 실행: NC_R=<자료 뿌리>/ NC_OUT=<패널 폴더> NC_FEAT=dropsig97 python3 f1_w47_최신기준_C2.py"""
import os, numpy as np, pandas as pd
from pathlib import Path
W47 = Path(__file__).with_name('w47_가격출발점_공급변화율.py')
g = {'__file__': str(W47), '__name__': '__main__'}
exec(compile(open(W47, encoding='utf-8').read(), str(W47), 'exec'), g)
OUTD = g['OUTD']; O = g['O']; fc = g['fc']; qs = g['qs']
C2 = lambda x: (x.f_섞기 + x.f_작년반반.fillna(x.f_섞기) + x.f_평균판) / 3   # 작년 같은 달 값이 없으면 작년반반 자리에 섞기(상황판 u10과 같은 처리)
O = O.copy(); O['f_섞기_w47'] = O.f_섞기; O['f_섞기'] = C2(O); O.to_pickle(OUTD / '_final_C2.pkl')
fc = fc.copy(); fc['f_섞기_w47'] = fc.f_섞기; fc['f_섞기'] = C2(fc)
# 80% 구간: w47과 같게 검증 해(2024) 잔차 분위(q10·q90, w47 섞기 기준)를 C2에 그대로 붙임 (상황판 u10과 같은 방식)
# 참고: 상황판(u10, 2026-09 기준) 앞으로 예측은 평균판 자리에 '계절+LGB 편차 전부'(f_가격없음LGB)를 썼음 → 같은 식 값을 따로 남김
lm_ = fc.f_가격없음LGB; fc['f_C2_상황판식'] = (fc.f_섞기_w47 + np.where(fc.ly_lp.notna(), 0.5 * fc.ly_lp + 0.5 * lm_, fc.f_섞기_w47) + lm_) / 3
fc['예측_원kg'] = np.exp(fc.f_섞기); fc['하한10'] = np.exp(fc.f_섞기 + fc.q10); fc['상한90'] = np.exp(fc.f_섞기 + fc.q90)
fc.to_pickle(OUTD / '_final_C2_최신기준.pkl')
print('C2 저장', len(O), '시험줄 | 최신 기준월', fc.기준월.iloc[0], len(fc), '줄', flush=True)

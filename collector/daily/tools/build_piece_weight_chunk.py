# -*- coding: utf-8 -*-
"""1개(포기)당 무게 기록을 달 묶음으로 채우기 (처음 한 번, 2020년부터. 11-10 추가)
  python tools/build_piece_weight_chunk.py 2020-01 2021-06
매일 실행은 build_tables.py 의 piece_weight 단계가 최근 달만 다시 계산함
"""
import sys, datetime as dt
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build_tables as B
a = dt.date.fromisoformat(sys.argv[1] + '-01'); b = dt.date.fromisoformat(sys.argv[2] + '-01')
B.t_piece_weight(a, b)

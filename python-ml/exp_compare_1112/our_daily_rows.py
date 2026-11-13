"""비교 실험용: 원인 모델 2_engine 을 그대로 돌리며 출발일 뒤 1~25일 예측(선택)을 줄 단위로 모음"""
import importlib.util, sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, sys.argv[1])
spec = importlib.util.spec_from_file_location("engine", Path(sys.argv[1]) / "2_engine.py")
E = importlib.util.module_from_spec(spec); spec.loader.exec_module(E)
ROWS = []
def hook(un, G, o, Tt, h, lv, L, tr, Cb, meth):
    k = h <= 25
    p = lv["선택"][k]; T = Tt[k]; ok = np.isfinite(p)
    for t, v in zip(T[ok], p[ok]):
        ROWS.append((un, G.days[o].date(), G.days[t].date(), float(v)))
E.main(sys.argv[2], None, hook)
pd.DataFrame(ROWS, columns=["단위", "출발", "목표일", "lp_원인"]).to_csv(sys.argv[3], index=False, compression="gzip")
print("줄", len(ROWS))

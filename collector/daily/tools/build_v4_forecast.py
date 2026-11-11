# -*- coding: utf-8 -*-
"""팀 v4(분석 상황판) 앞으로 12달 예측 → 화면 구조(품목 50 · 품종 196) 월 예측 표 price_forecast_monthly (11-11 추가)
  python tools/build_v4_forecast.py <fm_c.json>
  예) python tools/build_v4_forecast.py "D:\\nong-clock-data\\팀원이 보낸 데이터\\NongClock_최종모델링_1109\\결과\\상황판_데이터\\fm_c.json"
끝나면: python load_db.py --only price_forecast_monthly

fm_c.json = v4 최종판의 화면묶음(140 중 130)별 기준월 다음 달부터 12달 예측·하한·상한(원/kg). v4 는 지금·최근 가격을 입력에 안 씀.
규칙 (돌리기 전에 정함, 2026-11-11):
  1. 품종이 화면묶음 하나 그대로(예: 복숭아 가납암, 복숭아(기타))  → v4 묶음 예측 그대로
  2. 품목 이름 묶음을 쪼갠 품종(예: 복숭아 → 백도·황도·천도·털·천봉) → v4 묶음 예측 × (작년 같은 달 품종 단가 ÷ 묶음 단가).
     단가는 DB price_unit_daily 의 금액 합 ÷ 물량 합. 작년 같은 달 그 품종 거래가 없으면 넣지 않음
  3. 품목 전체(variety_id = 'ALL') → 예측 있는 묶음을 작년 같은 달 묶음 물량으로 가중 평균. 그 묶음들이 그 달 물량의 80% 미만이면 넣지 않음
  4. v4 가 그 달을 예측하지 않으면(출하철 밖) 넣지 않음 → 화면은 그 기간을 "예측 없음"으로
읽는 것: ref/unit_group_v3b.csv(예측단위 → 화면묶음, 팀 엑셀 50품목_화면묶음140_예측단위322_1110), shared/items50.json(품종), 표 폴더의 variety_unit · price_unit_daily
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import common as C

REPO = Path(__file__).resolve().parents[3]
MODEL = 'v4 (상황판 1109)'


def main(fm_path):
    fm = json.loads(Path(fm_path).read_text(encoding='utf-8'))
    items = json.loads((REPO / 'shared' / 'items50.json').read_text(encoding='utf-8'))['items']
    ug = pd.read_csv(C.HERE / 'ref' / 'unit_group_v3b.csv', dtype=str)
    u2g = dict(zip(ug.unit_name, ug.screen_group))
    g2units = ug.groupby('screen_group').unit_name.apply(list).to_dict()
    vu = pd.read_csv(C.OUT / 'variety_unit.csv', usecols=['unit_id', 'unit_name'])
    p = pd.read_csv(C.OUT / 'price_unit_daily.csv', usecols=['date', 'unit_id', 'volume_kg', 'amount_won'])
    p = p.merge(vu, on='unit_id')
    p['ym'] = p.date.str[:7]
    M = p.groupby(['unit_name', 'ym'])[['volume_kg', 'amount_won']].sum()

    def agg(units, ym):
        idx = [(u, ym) for u in units if (u, ym) in M.index]
        if not idx:
            return np.nan, 0.0
        x = M.loc[idx].sum()
        return (x.amount_won / x.volume_kg if x.volume_kg > 0 else np.nan), float(x.volume_kg)

    def parse(d):
        ms = d['월'].split(',')
        val = lambda k: [float(v) if v else np.nan for v in d[k].split(',')]
        return dict(zip(ms, zip(val('예측'), val('하한'), val('상한'))))

    FM = {d['예측단위']: parse(d) for d in fm}
    months = sorted({m for v in FM.values() for m in v})
    base = (pd.Period(months[0], 'M') - 1).strftime('%Y-%m-01')
    ly = lambda m: str(pd.Period(m, 'M') - 12)
    out = []

    def add(it, vid, m, pr, method):
        out.append(dict(base_month=base, item_code=it, variety_id=vid, target_month=m + '-01',
                        price=round(pr[0]), price_low=round(pr[1]), price_high=round(pr[2]), model=MODEL, method=method))

    for it in items:
        groups = set()
        for v in it['varieties']:
            g = u2g[v['units'][0]]
            groups.add(g)
            whole = len(g2units[g]) == len(v['units'])
            for m in months:
                pr = FM.get(g, {}).get(m)
                if pr is None or np.isnan(pr[0]):
                    continue
                if whole:
                    add(it['code'], v['id'], m, pr, 'v4 묶음 예측 그대로')
                    continue
                pv, _ = agg(v['units'], ly(m))
                pg, _ = agg(g2units[g], ly(m))
                if np.isnan(pv) or np.isnan(pg):
                    continue
                r = pv / pg
                add(it['code'], v['id'], m, [x * r for x in pr], f'v4 묶음 예측 × 작년 같은 달 품종/묶음 단가 {r:.3f}')
        # 품목 전체: 이 품목의 모든 화면묶음(예측단위 없는 묶음 포함) 물량으로 가중
        c4 = ug.loc[ug.unit_name == it['varieties'][0]['units'][0], 'code4'].iloc[0]
        allg = sorted(groups | set(ug[ug.code4 == c4].screen_group))
        for m in months:
            tot = sum(agg(g2units.get(g, []), ly(m))[1] for g in allg)
            w, vals = [], []
            for g in allg:
                pr = FM.get(g, {}).get(m)
                q = agg(g2units.get(g, []), ly(m))[1]
                if pr is not None and not np.isnan(pr[0]) and q > 0:
                    w.append(q); vals.append(pr)
            if tot <= 0 or sum(w) / tot < 0.8:
                continue
            W = np.array(w) / sum(w); a = np.array(vals)
            add(it['code'], 'ALL', m, [float((W * a[:, k]).sum()) for k in range(3)], f'v4 묶음 예측의 물량 가중 평균 (덮은 물량 {sum(w) / tot * 100:.0f}%)')
    df = pd.DataFrame(out)
    df.to_csv(C.OUT / 'price_forecast_monthly.csv', index=False, encoding='utf-8')
    print(f'price_forecast_monthly: {len(df):,}행 (기준월 {base}, 품목 {df[df.variety_id == "ALL"].item_code.nunique()}개, '
          f'품종 {df[df.variety_id != "ALL"].variety_id.nunique()}개) → {C.OUT}')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1])

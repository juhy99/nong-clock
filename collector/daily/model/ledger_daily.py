# -*- coding: utf-8 -*-
"""원장(수집기 data/raw/auction/YYYYMMDD.csv.gz) → 일별 품목코드 × 품종코드 국산 물량·금액 (오류 줄·오류 날 뺌). 2026-11-13
 76번 최종(104b → 104c)과 같은 규칙:
  ① 상위 50품목, 단위코드 12(kg), 물량·금액 > 0
  ② 줄 단위: 같은 달·품목코드·품종코드 거래 줄 안에서 줄 단가 < 중앙/8 이면서 줄 물량 > 중앙×8 인 줄을 뺌
  ③ 국산 = 산지명 첫 단어가 시·도 이름(또는 국내산·국산). 시장·공판장 이름·빈칸은 미상
  ④ 일 단위: 품종코드별 일 단가 < 앞뒤 61일 중앙/8 이면서 물량 > 중앙×8 인 날을 뺌
 --seed 는 ①~③까지만 건 과거 자료(104b). 받아 둔 과거는 그대로 두고, 수집기 원자료가 있는 달만 다시 계산해 덮어쓴다 (그 달 원자료 날 수가 seed보다 적으면 seed 유지)
 사용: python ledger_daily.py --raw <auction 폴더> --seed <일별 csv.gz> --top <상위50 csv> --out <출력 csv.gz> [--months 2]"""
import argparse, glob, os, sys
import numpy as np, pandas as pd
SIDO = ['서울', '부산', '대구', '인천', '광주', '대전', '울산', '세종', '경기', '강원', '충북', '충남', '전북', '전남', '경북', '경남', '제주', '충청', '전라', '경상']
COLS = ['정산일자', '대분류코드', '중분류코드', '소분류코드', '단위코드', '산지명', '총물량', '총금액']

def origin(name):
    s = str(name or '').strip()
    if not s or any(k in s for k in ('시장', '농수산', '공판장', '도매')) or s in ('서울특별시', '서울'): return '미상'
    head = s.split()[0]
    return '국산' if head.startswith('전남광주통합') or any(head.startswith(k) for k in SIDO) or head in ('국내산', '국산') else '수입'

def month_from_raw(files, top):
    parts = []
    for f in files:
        d = pd.read_csv(f, usecols=lambda c: c in COLS, dtype=str, encoding='utf-8-sig', keep_default_na=False, compression='gzip')
        miss = [c for c in COLS if c not in d.columns]
        if miss: sys.exit(f'[원장 열 없음] {os.path.basename(f)}: {miss}')
        d = d[d.단위코드 == '12']; d['품목코드4'] = d.대분류코드.str.zfill(2) + d.중분류코드.str.zfill(2); d = d[d.품목코드4.isin(top)]
        d = d.assign(q=pd.to_numeric(d.총물량, errors='coerce'), a=pd.to_numeric(d.총금액, errors='coerce')); parts.append(d[(d.q > 0) & (d.a > 0)])
    d = pd.concat(parts)
    if d.empty: return d, 0, 0.0
    d['품종코드'] = d.소분류코드.str.zfill(2); d['up'] = d.a / d.q
    g = d.groupby(['품목코드4', '품종코드']); mp = g.up.transform('median'); mq = g.q.transform('median')
    bad = (d.up < mp / 8) & (d.q > mq * 8); nb = int(bad.sum()); share = float(d.q[bad].sum() / d.q.sum() * 100); d = d[~bad]
    dom = d.산지명.map({u: origin(u) for u in d.산지명.unique()}) == '국산'
    d['qd'] = d.q.where(dom, 0.0); d['ad'] = d.a.where(dom, 0.0)
    r = d.groupby(['정산일자', '품목코드4', '품종코드'], as_index=False)[['q', 'a', 'qd', 'ad']].sum()
    r.columns = ['일자', '품목코드4', '품종코드', '물량_kg', '금액_원', '국산_kg', '국산금액_원']; r['일자'] = r.일자.str.replace('-', '').str[:8]
    return r, nb, share

def drop_bad_days(d):
    """④ 일 단위 오류: 국산 물량이 있는 날만 놓고, 품종코드별 단가·물량의 앞뒤 61줄(자료 있는 날) 중앙과 비교"""
    d = d.sort_values(['품목코드4', '품종코드', '일자']).reset_index(drop=True)
    x = d[d.국산_kg > 0]; p = x.국산금액_원 / x.국산_kg; g = [x.품목코드4, x.품종코드]
    mp = p.groupby(g).transform(lambda s: s.rolling(61, center=True, min_periods=10).median())
    mq = x.국산_kg.groupby(g).transform(lambda s: s.rolling(61, center=True, min_periods=10).median())
    bad = (p < mp / 8) & (x.국산_kg > mq * 8); idx = bad[bad].index
    return d.drop(idx), d.loc[idx].assign(p=p[idx], mp=mp[idx], mq=mq[idx])

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--raw'); ap.add_argument('--seed'); ap.add_argument('--top', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--months', type=int, default=2, help='원자료로 다시 계산할 최근 달 수'); ap.add_argument('--skip-day-rule', action='store_true')
    a = ap.parse_args(); top = set(pd.read_csv(a.top, dtype=str).품목코드4)
    dt = {'일자': str, '품목코드4': str, '품종코드': str}
    pre = a.out.replace('.csv.gz', '') + '_줄오류만.csv.gz'      # 일 단위 규칙을 걸기 전 상태를 따로 둔다 (규칙을 여러 번 걸면 중앙값이 달라지므로 항상 여기서 다시 건다)
    cols = ['일자', '품목코드4', '품종코드', '물량_kg', '금액_원', '국산_kg', '국산금액_원']
    base = pd.read_csv(a.seed, dtype=dt)[cols] if a.seed else pd.DataFrame(columns=cols)
    if os.path.exists(pre):
        prev = pd.read_csv(pre, dtype=dt)
        if not len(base) or prev.일자.max() >= base.일자.max(): base = prev
    base['ym'] = base.일자.str[:6]; note = []
    files = sorted(glob.glob(os.path.join(a.raw, '*.csv.gz'))) if a.raw else []
    by = {}
    for f in files: by.setdefault(os.path.basename(f)[:6], []).append(f)
    for ym in sorted(by)[-a.months:] if by else []:
        have = base[base.ym == ym].일자.nunique(); r, nb, share = month_from_raw(by[ym], top); got = r.일자.nunique() if len(r) else 0
        if got < have:      # 새 컴퓨터처럼 원자료가 그 달 일부만 있을 때: 가진 것은 두고, 그 뒤 날짜만 붙임
            lastd = base[base.ym == ym].일자.max(); r = r[r.일자 > lastd] if len(r) else r
            if len(r): base = pd.concat([base, r.assign(ym=ym)], ignore_index=True)
            note.append(f'{ym}: 원자료 {got}일 < 가진 것 {have}일 → 가진 것 유지' + (f', {lastd} 뒤 {r.일자.nunique()}일 붙임' if len(r) else '')); continue
        base = pd.concat([base[base.ym != ym], r.assign(ym=ym)], ignore_index=True); note.append(f'{ym}: 원자료 {got}일로 다시 계산 (뺀 줄 {nb}, 물량 {share:.3f}%)')
    base = base.drop(columns='ym').drop_duplicates(['일자', '품목코드4', '품종코드'], keep='last')
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True); base.sort_values(['일자', '품목코드4', '품종코드']).to_csv(pre + '.tmp', index=False, compression='gzip'); os.replace(pre + '.tmp', pre)
    nday = 0
    if not a.skip_day_rule:
        base, bad = drop_bad_days(base); nday = len(bad)
        bad.to_csv(os.path.splitext(os.path.splitext(a.out)[0])[0] + '_뺀_오류날.csv', index=False, encoding='utf-8-sig')
    base = base.sort_values(['일자', '품목코드4', '품종코드'])
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True); tmp = a.out + '.tmp'
    base.to_csv(tmp, index=False, compression='gzip'); os.replace(tmp, a.out)
    print(f'원장 일별: {len(base):,}줄 {base.일자.min()}~{base.일자.max()} | 일 단위 오류로 뺀 코드-날 {nday} | ' + ' / '.join(note or ['원자료로 다시 계산한 달 없음']), flush=True)

if __name__ == '__main__':
    main()

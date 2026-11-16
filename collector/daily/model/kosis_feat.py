# -*- coding: utf-8 -*-
"""통계청(KOSIS) 새 공표 → 면적·생산 변수 자동 반영. 2026-11-13
 26번 s3(생산 변수)와 같은 규칙으로 만든다:
  · 계열 ↔ 원천 매칭은 seed 의 01_계열_연도별_면적생산.csv 를 그대로 쓴다 (매칭키)
  · 매칭키 36개는 KOSIS 표 이름과 짝지어 둠 (ref/kosis_매칭.csv — 2018~2025 겹친 해에서 값 차이 0.01% 미만인 것만, 봄배추 = 일반봄배추+시설배추)
  · 새 해(01 표에 없는 해)가 KOSIS 에 나오면 그 해 면적·생산량과 전년비를 붙인다
  · 쓸 수 있는 날 = max(s3 의 공표 시기 규칙, 이 컴퓨터가 처음 받은 날)  → 학습 때와 같은 규칙이고 미래 정보를 쓰지 않음
  · 그다음 s3 와 같은 식(그 달 말에 쓸 수 있는 최신 해)으로 생산_* 열을 다시 계산. 면적매달_* 열(관측월보 면적)은 그대로 이어 씀
 KOSIS 에 없는 원천(마늘·양파 숙기별, 사과·배 품종별 면적, 가지·멜론·부추·미나리·파프리카)은 마지막 공표 값을 그대로 이어 씀
 사용: python kosis_feat.py <KOSIS 원자료 폴더> <자료뿌리 폴더> <기준월 YYYY-MM> <ref 폴더> <상태 json>
       python kosis_feat.py --check <자료뿌리 폴더> <ref 폴더>     ← 새 해 없이 다시 계산해서 지금 파일과 같은지 확인"""
import datetime as dt, json, os, sys
import numpy as np, pandas as pd

P26 = os.path.join('26_품종구분_전처리_변수', '04_변수_생산', '02_계열_월별_사용가능_생산피처.csv.gz')
PC = ['생산_최신연도', '생산_면적_ha', '생산_생산량_t', '생산_면적_전년비_%', '생산_생산량_전년비_%', '생산_시설비중_%', '생산_매칭수준']

def avail_rule(src, key, y):
    """26번 s3 avail() 그대로 (공표 시기 규칙)"""
    if src.startswith('43'): return f'{y + 1}-10-31'
    if src.startswith('40 통계청'): return f'{y}-07-31'
    if src.startswith('40 관측월보'): return f'{y + 1}-06-30'
    if src.startswith('08 KOSIS 서류'): return f'{y}-09-30' if key == '봄감자' else f'{y}-12-31'
    if src.startswith('08 KOSIS 과실'): return f'{y}-12-31' if key in ('사과', '배') else f'{y + 1}-06-30'
    return f'{y + 1}-10-31'

def read_kosis(raw):
    """kosis_auto 원자료 → (TBL, 이름, 연도) × 면적·생산량 (전국)"""
    out = []
    for tbl in ('DT_1ET0026', 'DT_1ET0027', 'DT_1ET0028', 'DT_1ET0029', 'DT_1ET0291', 'DT_1ET0292'):
        f = os.path.join(raw, tbl, tbl + '.csv')
        if not os.path.exists(f): continue
        x = pd.read_csv(f, dtype=str)
        x = x[x.C1_NM.isin(['전국', '계'])].copy()
        x[['이름', '지표']] = x.ITM_NM.str.split(':', n=1, expand=True)
        x = x[x.지표.isin(['면적', '생산량'])]; x['v'] = pd.to_numeric(x.DT, errors='coerce')
        out.append(x.assign(TBL=tbl, 연도=x.PRD_DE.astype(int))[['TBL', '이름', '연도', '지표', 'v']])
    if not out: return pd.DataFrame(columns=['TBL', '이름', '연도', '면적', '생산량'])
    X = pd.concat(out).pivot_table(index=['TBL', '이름', '연도'], columns='지표', values='v', aggfunc='first').reset_index()
    return X

def kosis_year_values(X, M):
    """매칭키 × 연도 → 면적·생산량 (이름이 'a+b' 면 합)"""
    rows = []
    for r in M.itertuples():
        parts = r.KOSIS이름.split('+'); g = X[(X.TBL == r.TBL) & X.이름.isin(parts)]
        if g.empty: continue
        s = g.groupby('연도')[['면적', '생산량']].sum(min_count=1)
        cnt = g.groupby('연도').이름.nunique(); s = s[cnt.reindex(s.index) == len(parts)]
        for y, v in s.iterrows(): rows.append((r.매칭키, r.출처, int(y), v.면적, v.생산량))
    return pd.DataFrame(rows, columns=['매칭키', '출처', '연도', '면적_ha', '생산량_t'])

def extend_years(Y, K, first_seen):
    """01 표(Y)에 KOSIS 새 해를 붙임. first_seen: {'매칭키|연도': 'YYYY-MM-DD'}"""
    have = set(zip(Y.매칭키, Y.연도)); last = Y.groupby('매칭키').연도.max().to_dict(); new = []
    meta = Y.sort_values('연도').drop_duplicates('계열키', keep='last')
    for key, g in K.groupby('매칭키'):
        g = g.set_index('연도').sort_index()
        for y in g.index:
            if key not in last or y <= last[key] or (key, y) in have or (y - 1) not in g.index: continue   # 01 표 마지막 해 뒤의 새 해만
            seen = first_seen.setdefault(f'{key}|{y}', dt.date.today().isoformat())
            for r in meta[meta.매칭키 == key].itertuples(index=False):
                d = r._asdict(); a0, p0 = g.at[y - 1, '면적_ha'], g.at[y - 1, '생산량_t']; a1, p1 = g.at[y, '면적_ha'], g.at[y, '생산량_t']
                d.update(연도=y, 면적_ha=a1, 생산량_t=p1, **{'면적_ha_전년비_%': round((a1 / a0 - 1) * 100, 2) if a0 else np.nan,
                                                       '생산량_t_전년비_%': round((p1 / p0 - 1) * 100, 2) if p0 else np.nan},
                         사용가능일=max(avail_rule(r.출처, key, y), seen), 사용가능일_근거=f'KOSIS 자동: 공표 규칙과 처음 받은 날({seen}) 중 늦은 날')
                new.append(d)
    return (pd.concat([Y, pd.DataFrame(new)], ignore_index=True) if new else Y), len(new)

def monthly(Y, months):
    """s3 와 같은 식: 그 달 말에 쓸 수 있는 최신 해 값"""
    Y = Y.copy(); Y['_d'] = pd.to_datetime(Y['사용가능일'])
    T = pd.DataFrame([(k, str(p)) for k in Y['계열키'].unique() for p in months], columns=['계열키', '연월'])
    T['_e'] = pd.PeriodIndex(T['연월'], freq='M').to_timestamp(how='end')
    T = T.sort_values('_e'); Ys = Y.sort_values('_d')
    M = pd.merge_asof(T, Ys[['계열키', '_d', '연도', '면적_ha', '생산량_t', '면적_ha_전년비_%', '생산량_t_전년비_%', '시설비중_%', '매칭수준']],
                      left_on='_e', right_on='_d', by='계열키', direction='backward')
    M = M.dropna(subset=['연도']).rename(columns={'연도': '생산_최신연도', '면적_ha': '생산_면적_ha', '생산량_t': '생산_생산량_t',
         '면적_ha_전년비_%': '생산_면적_전년비_%', '생산량_t_전년비_%': '생산_생산량_전년비_%', '시설비중_%': '생산_시설비중_%', '매칭수준': '생산_매칭수준'})
    return M.drop(columns=['_e', '_d'])

def rebuild(R, Y, base):
    """자료뿌리의 02 파일에서 생산_* 열만 다시 계산 (복제 계열 포함), 면적매달_* 열은 이어 씀"""
    f = os.path.join(R, P26); A = pd.read_csv(f, low_memory=False)
    months = pd.period_range(A.연월.min(), max(A.연월.max(), base), freq='M')
    M = monthly(Y, months)
    # 자료뿌리에는 01 표에 없는 복제 계열(새 단위 키에 옛 키 값을 복제)이 있음 → 옛 계열 찾기
    own = set(Y.계열키); sig = lambda x: tuple(x.sort_values('연월')[['연월', '생산_생산량_t', '생산_면적_ha']].round(1).astype(str).agg('|'.join, axis=1))
    src = {}
    for k, x in A[A.계열키.isin(own) & A.생산_생산량_t.notna()].groupby('계열키'): src.setdefault(sig(x), k)
    clone = {}
    for k, x in A[~A.계열키.isin(own) & A.생산_생산량_t.notna()].groupby('계열키'):
        o = src.get(sig(x))
        if o: clone[k] = o
    M = pd.concat([M] + [M[M.계열키 == o].assign(계열키=k) for k, o in clone.items()], ignore_index=True)
    rest = [c for c in A.columns if c not in PC and c not in ('계열키', '연월')]
    B = A[['계열키', '연월'] + rest]
    # 새 달: 면적매달 열은 계열마다 마지막 값을 이어 씀
    lastm = A.연월.max(); add = [str(p) for p in months if str(p) > lastm]
    if add:
        L = B[B.연월 == lastm]; B = pd.concat([B] + [L.assign(연월=m) for m in add], ignore_index=True)
    keep_other = A[~A.계열키.isin(own | set(clone))]            # 01 표와 연결 안 된 계열(84 채움 등)은 그대로
    N = B.merge(M, on=['계열키', '연월'], how='outer')
    N = N[N.계열키.isin(own | set(clone))]
    if add:
        ko = keep_other[keep_other.연월 == lastm]; keep_other = pd.concat([keep_other] + [ko.assign(연월=m) for m in add], ignore_index=True)
    o = A[['계열키', '연월', '생산_최신연도', '생산_시설비중_%']].rename(columns={'생산_최신연도': '_y', '생산_시설비중_%': '_s'}).drop_duplicates(['계열키', '연월'])   # 시설비중: 01 표는 소수 2자리라 같은 해면 원래 값 유지
    N = N.merge(o, on=['계열키', '연월'], how='left'); hit = N._y.notna() & (N._y == N.생산_최신연도)
    N.loc[hit, '생산_시설비중_%'] = N.loc[hit, '_s']; N = N.drop(columns=['_y', '_s'])
    N = pd.concat([N, keep_other], ignore_index=True)[A.columns]
    return A, N.sort_values(['계열키', '연월']).reset_index(drop=True), len(clone)

def same(A, N):
    k = ['계열키', '연월']; a = A.sort_values(k).reset_index(drop=True); n = N[N.연월 <= A.연월.max()].sort_values(k).reset_index(drop=True)
    if len(a) != len(n) or not (a[k].values == n[k].values).all(): return False, f'줄 수 {len(a)} vs {len(n)}'
    bad = 0
    for c in A.columns:
        if c in k: continue
        x, y = a[c], n[c]
        if x.dtype.kind in 'fi' and y.dtype.kind in 'fi': bad += int((~np.isclose(x, y, equal_nan=True, atol=1e-6)).sum())
        else: bad += int(((x.astype(object).where(x.notna(), None) != y.astype(object).where(y.notna(), None)) & ~(x.isna() & y.isna())).sum())
    return bad == 0, f'다른 칸 {bad}'

if __name__ == '__main__':
    if sys.argv[1] == '--check':
        R, REF = sys.argv[2], sys.argv[3]; Y = pd.read_csv(os.path.join(REF, '01_계열_연도별_면적생산.csv'))
        A, N, nc = rebuild(R, Y, pd.read_csv(os.path.join(R, P26), usecols=['연월']).연월.max())
        ok, msg = same(A, N); print('다시 계산 = 지금 파일:', ok, msg, '| 복제 계열', nc); sys.exit(0 if ok else 1)
    RAW, R, BASE, REF, STATE = sys.argv[1:6]
    Y = pd.read_csv(os.path.join(REF, '01_계열_연도별_면적생산.csv'))
    YE = os.path.join(os.path.dirname(STATE), '01_계열_연도별_면적생산_KOSIS자동.csv')
    if os.path.exists(YE): Y = pd.read_csv(YE)
    st = json.load(open(STATE, encoding='utf-8')) if os.path.exists(STATE) else {}
    X = read_kosis(RAW)
    if X.empty: print('통계청: KOSIS 원자료 없음 (collect_monthly.py kosis 가 아직 안 돌았거나 실패) → 지난 값 그대로'); sys.exit(0)
    K = kosis_year_values(X, pd.read_csv(os.path.join(REF, 'kosis_매칭.csv')))
    Y2, n = extend_years(Y, K, st)
    json.dump(st, open(STATE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    if n: Y2.to_csv(YE, index=False, encoding='utf-8-sig')
    A, N, nc = rebuild(R, Y2, BASE)
    N.to_csv(os.path.join(R, P26), index=False, compression='gzip')
    newk = sorted({k.split('|')[0] for k in st}) if n else []
    print(f'통계청 자동: 새 해 줄 {n} (계열 기준) · KOSIS 마지막 해 {int(K.연도.max())} · 다시 계산 {N.연월.min()}~{N.연월.max()} · 복제 계열 {nc}' + (f' · 새로 들어온 매칭키 {len(newk)}' if n else ''))

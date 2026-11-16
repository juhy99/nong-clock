# -*- coding: utf-8 -*-
"""새로 들어온 자료를 모델 변수(자료뿌리)에 넣기. 2026-11-13   (feat_roll.py 보다 먼저 돈다)
  ① 주산지 기상(97): 수집기 data/raw/juju/YYYYMM.json.gz → 다 찬 달만 계열 × 달 값으로 (97번 전처리와 같은 식) — 완전 자동
  ② 월보 신호(83): wolbo_auto.py 가 PDF 에서 뽑은 생산 전망(_처리/월보_자동_*.csv) + (있으면) 월보_추가.csv 에 사람이 적은 값을 월보 입력 2개에 더하고 신호를 처음부터 다시 계산 (83번 전처리와 같은 식)
  ③ 통계청 공표: kosis_feat.py 가 KOSIS 원자료로 새 해를 자동 반영 → (있으면) 공표_추가.csv 에 사람이 적은 값을 덮어씀
 사용: python feat_update.py <자료뿌리 폴더> <모델 작업 폴더(tV 또는 tW)> <수집기 자료 폴더(data)> <기준월 YYYY-MM> <ref 폴더> <code 폴더>
 월보_추가.csv · 공표_추가.csv 는 자동 추출이 틀렸을 때 고치는 용도(보통은 비워 둠). 양식은 처음 돌 때 빈 파일로 만들어 둔다"""
import glob, gzip, json, os, sys
import numpy as np, pandas as pd

P97 = os.path.join('00_기본자료', '02_전처리', '97_농업주산지_품종기상', '03_계열_월별_주산지기상_2015_2026.csv')
P83 = os.path.join('00_기본자료', '02_전처리', '83_품종_월보생산전망_신호', '01_계열_기준월_목표월_월보신호.csv.gz')
P26 = os.path.join('26_품종구분_전처리_변수', '04_변수_생산', '02_계열_월별_사용가능_생산피처.csv.gz')
KEYS = ['areaId', 'areaName', 'paCropName', 'paCropSpeId', 'paCropSpeName']

def juju_month(d):
    """일통계 줄(한 달 이상) → 주산지 × 작물 × 품종작형 × 달 (p97 과 같은 식)"""
    d = d.copy(); d['areaId'] = d.areaId.astype(str); d['날짜'] = pd.to_datetime(d['ymd']).dt.date; d['연월'] = pd.to_datetime(d['ymd']).dt.strftime('%Y-%m')
    for c in ('dayAvgTa', 'dayMaxTa', 'dayMinTa', 'daySumRn', 'daySumSs', 'dayAvgRhm', 'dayMinRhm', 'dayAvgWs'): d[c] = pd.to_numeric(d[c], errors='coerce')
    d = d.drop_duplicates(KEYS + ['날짜'])
    d.loc[d['dayAvgRhm'] <= 0, 'dayAvgRhm'] = np.nan
    d['wrn'] = d['wrnCd'].fillna('').astype(str).str.strip().replace('nan', '')
    for k, nm in {'H': '폭염', 'C': '한파', 'R': '호우', 'W': '강풍', 'D': '건조', 'S': '대설', 'T': '태풍'}.items(): d['특보일_' + nm] = d['wrn'].str.contains(k).astype(int)
    d['특보일_전체'] = (d['wrn'] != '').astype(int)
    g = d.groupby(KEYS + ['연월']).agg(일수=('날짜', 'nunique'), 평균기온=('dayAvgTa', 'mean'), 최고기온_월최대=('dayMaxTa', 'max'), 최저기온_월최소=('dayMinTa', 'min'),
                                     최고기온_평균=('dayMaxTa', 'mean'), 최저기온_평균=('dayMinTa', 'mean'), 강수합=('daySumRn', 'sum'), 일조합=('daySumSs', 'sum'),
                                     평균습도=('dayAvgRhm', 'mean'), 평균풍속=('dayAvgWs', 'mean'),
                                     고온일_33도=('dayMaxTa', lambda s: int((s >= 33).sum())), 영하일=('dayMinTa', lambda s: int((s < 0).sum())),
                                     강수일_1mm=('daySumRn', lambda s: int((s >= 1).sum())),
                                     **{c: (c, 'sum') for c in d.columns if c.startswith('특보일_')}).reset_index()
    return g.rename(columns={'areaId': '주산지코드', 'areaName': '주산지', 'paCropName': '작물', 'paCropSpeId': '품종코드_기상청', 'paCropSpeName': '품종작형'})

def juju_series(g, LK):
    """→ 계열 × 달 (주산지 평균). p97 은 01 파일(소수 2자리)에서 평균했으므로 같게 맞춤"""
    g = g.copy(); num = [c for c in g.columns if g[c].dtype != object]; g[num] = g[num].round(2)
    g['품종작형'] = g['품종작형'].astype(str).str.strip()
    X = g.merge(LK[LK['계열키'].notna()], on=['작물', '품종작형'])
    S = X.groupby(['계열키', '연결수준', '연월'])[num].mean(); S['주산지수'] = X.groupby(['계열키', '연결수준', '연월'])['주산지코드'].nunique()
    S = S.reset_index(); S['사용가능월'] = (pd.PeriodIndex(S['연월'], freq='M') + 1).astype(str); return S.round(2)

def clone_map(A, base_keys):
    """seed 에서 다른 계열 값을 그대로 복제해 쓰는 계열 찾기: {복제 계열: 원래 계열}"""
    cols = [c for c in A.columns if c not in ('계열키',)]; sig = {}
    for k, x in A.groupby('계열키'):
        sig[k] = hash(x[cols].sort_values('연월').round(2).astype(str).agg('|'.join, axis=1).str.cat(sep='\n'))
    src = {sig[k]: k for k in sig if k in base_keys}
    return {k: src[s] for k, s in sig.items() if k not in base_keys and s in src}

def update_juju(R, DATA, BASE, REF):
    f = os.path.join(R, P97); A = pd.read_csv(f); raw = sorted(glob.glob(os.path.join(DATA, 'raw', 'juju', '*.json.gz')))
    have = A.loc[A.일수 >= 28, '연월'].max(); todo = [p for p in raw if have < f'{os.path.basename(p)[:4]}-{os.path.basename(p)[4:6]}' <= BASE]
    if not todo: return print(f'주산지 기상: 새로 넣을 달 없음 (다 찬 달 {have}까지, 받아 둔 원자료 {len(raw)}달)')
    LK = pd.read_csv(os.path.join(REF, '04_품종작형_계열연결표.csv'), dtype=str); LK['품종작형'] = LK['품종작형'].astype(str).str.strip()
    cm = clone_map(A[A.연월 <= have], set(LK.계열키.dropna())); new = []
    for p in todo:
        d = pd.DataFrame(json.load(gzip.open(p, 'rt', encoding='utf-8')))
        if d.empty: continue
        S = juju_series(juju_month(d), LK); S = S[S.일수 >= 28]      # 다 찬 달만
        if len(S): new.append(pd.concat([S] + [S[S.계열키 == o].assign(계열키=k) for k, o in cm.items()]))
    if not new: return print('주산지 기상: 원자료는 있으나 다 찬 달이 없음')
    N = pd.concat(new); A = pd.concat([A[~A.연월.isin(N.연월.unique())], N[A.columns]], ignore_index=True).sort_values(['계열키', '연월'])
    A.to_csv(f, index=False, encoding='utf-8-sig', float_format='%.2f'); print(f'주산지 기상: {sorted(N.연월.unique())} 넣음 ({N.계열키.nunique()}계열, 복제 {len(cm)}계열)')

def wolbo_signal(K, W, F, VV, CAL, t_last):
    """83번 p83 과 같은 식. K = 계열키·품목명·계열"""
    W = W[(W.지표 == 'prod') & (W.전년비_pct.abs() <= 80)].copy(); W['mi'] = W.발행.str[:4].astype(int) * 12 + W.발행.str[5:7].astype(int) - 1; W['pct'] = W.전년비_pct.clip(-40, 40)
    Wg = {k: g.sort_values('mi')[['mi', 'pct']].values for k, g in W.groupby(['품목', '작형'])}
    NM = {'봄': '봄', '고냉지': '고랭지', '여름': '고랭지', '김장(가을': '가을', '가을': '가을', '월동': '겨울', '조생': '조생', '만생': '중만생', '중만생': '중만생', '중생': '중만생'}
    ST = {'사과': 8, '배': 8, '단감': 7, '포도': 3}
    F = F[(F.지표 == '생산량') & (F.발행월 >= 5) & (F.전년비_pct.abs() <= 60) & F.품목.isin(ST)].copy(); F['mi'] = F.연도 * 12 + F.발행월 - 1
    Fg = {k: g[['연도', 'mi', '전년비_pct']].values for k, g in F.groupby('품목')}
    VV = VV.dropna(subset=['dq', 'dp']); BF = {it: (g.dq * g.dp).sum() / (g.dq ** 2).sum() for it, g in VV[VV.시즌 <= 2018].groupby('품목')}
    def veg(it, ser, t, m):
        mon = m % 12 + 1; yr = m // 12
        for (i, cr), ms in CAL.items():
            if i != it or mon not in ms: continue
            if ser in NM and NM[ser] != cr: return None
            s = ms[0]; Y = yr if mon >= s else yr - 1; use = cr; st = Y * 12 + s - 1
            if it == '감자' and cr == '가을': use = '고랭지'; st = Y * 12 + CAL[('감자', '고랭지')][0] - 1
            a = Wg.get((it, use))
            if a is None: return None
            x = a[(a[:, 0] >= st - 8) & (a[:, 0] <= min(t, st + 1))]
            if len(x) == 0: return (cr, use, Y, np.nan, np.nan)
            last = x[:, 0].max(); return (cr, use, Y, float(np.median(x[x[:, 0] == last, 1])), int(last))
        return None
    def fruit(it, t, m):
        mon = m % 12 + 1; yr = m // 12; SY = yr if mon >= ST[it] else yr - 1; a = Fg[it]
        x = a[(a[:, 0] == SY) & (a[:, 1] <= t)]
        if len(x) == 0: return ('시즌', '시즌', SY, np.nan, np.nan)
        last = x[:, 1].max(); return ('시즌', '시즌', SY, float(np.median(x[x[:, 1] == last, 2])), int(last))
    VEG = {k[0] for k in CAL}; rows = []
    for r in K[K.품목명.isin(VEG | set(ST))].itertuples():
        for t in range(2018 * 12, t_last + 1):
            for h in range(1, 13):
                m = t + h; res = veg(r.품목명, r.계열, t, m) if r.품목명 in VEG else fruit(r.품목명, t, m)
                if res is None: continue
                cr, use, Y, pct, last = res; b = 0.5 * -1.689 if r.품목명 in VEG else BF[r.품목명]
                rows.append((r.계열키, r.품목명, r.계열, f'{t // 12}-{t % 12 + 1:02d}', h, f'{m // 12}-{m % 12 + 1:02d}', '채소 작형' if r.품목명 in VEG else '과일 시즌', cr, use, Y, pct,
                             np.nan if np.isnan(last) else f'{int(last) // 12}-{int(last) % 12 + 1:02d}', b))
    D = pd.DataFrame(rows, columns=['계열키', '품목명', '계열', '기준월', 'h', '목표월', '종류', '작형_시즌', '쓴전망', '작형해', '생산전망_전년비_pct', '쓴호', '탄력b(참고)'])
    D['신호_log'] = np.log1p(D.생산전망_전년비_pct / 100).round(4); D['가격조정(참고)=b×신호'] = (D['탄력b(참고)'] * D.신호_log).round(4); return D

def load_cal(CODE):
    src = open(os.path.join(CODE, 'w18_채소_작형시즌_월보전망_가격.py'), encoding='utf-8').read()
    return eval(src[src.index('CAL = {') + 6: src.index('}', src.index('CAL = {')) + 1])

def update_wolbo(R, WORK, DATA, BASE, CODE, check_only=False):
    f = os.path.join(R, P83); old = pd.read_csv(f); K = old.drop_duplicates('계열키')[['계열키', '품목명', '계열']]
    fw = os.path.join(WORK, '_입력', '월보_작형별_수급지표_35_05.csv'); ff = os.path.join(WORK, '_입력', '월보_과일5_생산_재추출.csv'); W = pd.read_csv(fw); F = pd.read_csv(ff)
    add = os.path.join(DATA, 'manual', '월보', '월보_추가.csv'); os.makedirs(os.path.dirname(add), exist_ok=True); n = 0
    if not os.path.exists(add):
        open(add, 'w', encoding='utf-8-sig').write('품목,작형,발행,생산전망_전년비_pct,출처\n')   # 예: 배추,겨울,2026-12,-3.5,12월호 5쪽 / 사과,,2026-12,4.1,12월호 (과일은 작형 빈칸)
    A = pd.read_csv(add, dtype=str).dropna(subset=['품목', '발행', '생산전망_전년비_pct'])
    for r in A.itertuples():
        pct = float(r.생산전망_전년비_pct); cr = '' if pd.isna(r.작형) else str(r.작형).strip()
        if cr:
            if not ((W.품목 == r.품목) & (W.작형 == cr) & (W.발행 == r.발행) & (W.지표 == 'prod') & (W.출처.astype(str) == '수동:' + str(r.출처))).any():
                W = pd.concat([W, pd.DataFrame([{'품목': r.품목, '작형': cr, '지표': 'prod', '발행': r.발행, '전년비_pct': pct, '출처': '수동:' + str(r.출처)}])], ignore_index=True); n += 1
        else:
            y, mth = int(r.발행[:4]), int(r.발행[5:7])
            if not ((F.품목 == r.품목) & (F.연도 == y) & (F.발행월 == mth) & (F.지표 == '생산량') & (F.방식.astype(str) == '수동')).any():
                F = pd.concat([F, pd.DataFrame([{'연도': y, '발행월': mth, '파일': str(r.출처), '페이지': '', '품목': r.품목, '지표': '생산량', '전년비_pct': pct, '방식': '수동', '원문': ''}])], ignore_index=True); n += 1
    auto = os.path.join(DATA, 'manual', '월보', '_처리'); na = 0          # wolbo_auto.py 가 PDF 에서 자동으로 뽑은 것 (새 호만 더함)
    fa = os.path.join(auto, '월보_자동_작형.csv')
    if os.path.exists(fa):
        A_ = pd.read_csv(fa); key = ['품목', '작형', '지표', '발행']; A_ = A_[~A_.set_index(key).index.isin(W.set_index(key).index)]
        if len(A_): W = pd.concat([W, A_.assign(출처='자동:' + A_.출처.astype(str))], ignore_index=True); na += len(A_)
    fa = os.path.join(auto, '월보_자동_과일.csv')
    if os.path.exists(fa):
        A_ = pd.read_csv(fa); have = set(zip(F.연도, F.발행월, F.품목)); A_ = A_[[(a, b, c) not in have for a, b, c in zip(A_.연도, A_.발행월, A_.품목)]]
        if len(A_): F = pd.concat([F, A_[F.columns]], ignore_index=True); na += len(A_)
    n += na
    if n and not check_only: W.to_csv(fw, index=False, encoding='utf-8-sig'); F.to_csv(ff, index=False, encoding='utf-8-sig')
    VV = pd.read_csv(os.path.join(R, '68_시즌단위_과일품종_사과배단감', '15_가락장기_2025까지_품종시즌_가격물량.csv'))
    t_last = int(BASE[:4]) * 12 + int(BASE[5:7]) - 1; D = wolbo_signal(K, W, F, VV, load_cal(CODE), t_last)
    c = old.merge(D, on=['계열키', '기준월', 'h'], how='inner', suffixes=('_옛', '')); same = np.isclose(c.신호_log_옛.fillna(-9), c.신호_log.fillna(-9), atol=1e-4).mean()
    if check_only: return len(old), len(D[D.기준월 <= old.기준월.max()]), float(same)
    D.to_csv(f, index=False, encoding='utf-8-sig', compression='gzip')
    print(f'월보 신호: 다시 계산 {old.기준월.max()} → {D.기준월.max()} ({len(D):,}줄, 새로 더한 전망 {n}개(PDF 자동 {na}개), 겹치는 줄 중 예전과 같은 값 {same * 100:.2f}%)')

def update_stat_auto(R, DATA, BASE, REF):
    """KOSIS 원자료(collect_monthly.py kosis) → 면적·생산 변수 자동 (kosis_feat.py)"""
    import subprocess
    raw = os.path.join(DATA, 'raw', 'kosis')
    if not os.path.isdir(raw): return print('통계청 자동: KOSIS 원자료 없음 (collect_monthly.py kosis 가 아직 안 돌았음) → 지난 공표 값 그대로')
    r = subprocess.run([sys.executable, '-X', 'utf8', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'kosis_feat.py'), raw, R, BASE, REF,
                        os.path.join(raw, f'_처음받은날_{os.path.basename(os.path.normpath(R))}.json')], capture_output=True, text=True, encoding='utf-8', errors='replace')
    print((r.stdout or '').strip())
    if r.returncode != 0: raise SystemExit('[통계청 자동 실패] ' + ((r.stderr or r.stdout).strip().splitlines() or ['?'])[-1])

def update_stat(R, DATA, BASE):
    add = os.path.join(DATA, 'manual', '통계청', '공표_추가.csv'); os.makedirs(os.path.dirname(add), exist_ok=True)
    if not os.path.exists(add):
        open(add, 'w', encoding='utf-8-sig').write('품목코드4,쓸수있는달,생산_면적_전년비_%,생산_생산량_전년비_%,면적매달_전년비_%,출처\n')   # 예: 1001,2026-12,-2.1,3.4,-2.1,2026 가을배추 생산량 12-20 공표  (모르는 칸은 빈칸 = 안 바꿈)
    A = pd.read_csv(add, dtype=str).dropna(subset=['품목코드4', '쓸수있는달'])
    if A.empty: return print('통계청 공표: 새로 적은 값 없음')
    f = os.path.join(R, P26); X = pd.read_csv(f, dtype=str, keep_default_na=False); n = 0
    last = X.연월.max()
    m = last
    while m < BASE:                                   # 덮어쓸 달이 있어야 하므로 먼저 이어 붙임
        m = str(pd.Period(m, freq='M') + 1); X = pd.concat([X, X[X.연월 == last].assign(연월=m)], ignore_index=True)
    for _, r in A.iterrows():
        hit = X.계열키.str.startswith(str(r['품목코드4']).zfill(4) + '|') & (X.연월 >= r['쓸수있는달'])
        for c in ('생산_면적_전년비_%', '생산_생산량_전년비_%', '면적매달_전년비_%'):
            v = r.get(c)
            if isinstance(v, str) and v.strip(): X.loc[hit, c] = v.strip()
        n += int(hit.sum())
    X.to_csv(f, index=False, compression='gzip'); print(f'통계청 공표: 적은 값 {len(A)}줄 → 계열-달 {n}칸에 반영')

if __name__ == '__main__':
    R, WORK, DATA, BASE, REF, CODE = sys.argv[1:7]
    update_juju(R, DATA, BASE, REF); update_wolbo(R, WORK, DATA, BASE, CODE); update_stat_auto(R, DATA, BASE, REF); update_stat(R, DATA, BASE)

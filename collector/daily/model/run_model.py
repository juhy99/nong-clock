# -*- coding: utf-8 -*-
"""모델 자동 실행 (76번 최종과 같은 코드·규칙). 2026-11-13
  python model/run_model.py daily      # 원장 전처리 → 322 일별 가격 → 일·주 예측(u7d) → 365일 일별 → 결과 묶음
  python model/run_model.py monthly    # (월 1회, 3~5일) 월 패널 → v4 · 부모 v4 → 단위별 모델(고정) → 월 예측 12달  + daily
  옵션: --base YYYY-MM (기준월 직접 지정) · --raw <auction 폴더> · --data <작업 폴더, 기본 data/model>
 단위별 모델(v4 256 · 따라 43 · 반반 23)·출하철·단위 정의는 고정(model/ref). 다시 고르지 않는다.
 결과: <작업 폴더>/결과/NongClock_자동_기준YYYYMM/ (76번 묶음과 같은 모양 → db/make_db_csv.py 가 읽음)"""
import argparse, glob, os, shutil, subprocess, sys, time
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); CODE = os.path.join(HERE, 'code'); REF = os.path.join(HERE, 'ref'); SEED = os.path.join(HERE, 'seed')
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument('mode', choices=['daily', 'monthly']); ap.add_argument('--base'); ap.add_argument('--raw', default=os.path.join(ROOT, 'data', 'raw', 'auction'))
ap.add_argument('--data', default=os.path.join(ROOT, 'data', 'model')); ap.add_argument('--no-raw', action='store_true', help='수집기 원자료를 읽지 않고 가진 원장으로만')
a = ap.parse_args(); D = a.data; W = os.path.join(D, 'work'); os.makedirs(W, exist_ok=True); PY = [sys.executable, '-X', 'utf8']

def run(name, cmd, cwd=CODE, env=None, log=None):
    t0 = time.time(); print(f'▶ {name}', flush=True)
    e = dict(os.environ, PYTHONIOENCODING='utf-8', **(env or {}))
    r = subprocess.run(cmd, cwd=cwd, env=e, capture_output=True, text=True, encoding='utf-8', errors='replace')
    out = (r.stdout or '') + (r.stderr or '')
    if log: open(log, 'w', encoding='utf-8').write(out)
    tail = [l for l in out.strip().splitlines() if l.strip()][-3:]
    if r.returncode != 0:
        print('\n'.join(out.strip().splitlines()[-15:])); sys.exit(f'[모델 단계 실패] {name} (종료코드 {r.returncode})')
    print('   ' + '\n   '.join(x[:200] for x in tail), f'({time.time() - t0:.0f}초)', flush=True)

def seed_once():
    """처음 한 번: 넣어 둔 seed(76번 최종 상태)를 작업 폴더로"""
    for t in ('tV', 'tW'):
        if not os.path.exists(os.path.join(W, t)): shutil.copytree(os.path.join(SEED, t), os.path.join(W, t))
        if not os.path.exists(os.path.join(D, f'자료뿌리_{t}')): shutil.copytree(os.path.join(SEED, f'자료뿌리_{t}'), os.path.join(D, f'자료뿌리_{t}'))
seed_once()
LED = os.path.join(D, 'ledger', '원장_일별_품종코드.csv.gz'); UNIT = os.path.join(D, 'unit', '322_일별가격.csv.gz'); os.makedirs(os.path.dirname(UNIT), exist_ok=True)

# 1) 원장 전처리 (오류 줄·오류 날)
cmd = PY + [os.path.join(HERE, 'ledger_daily.py'), '--seed', os.path.join(SEED, '원장_일별_줄오류만_seed.csv.gz'), '--top', os.path.join(REF, '상위50_품목코드.csv'), '--out', LED]
if not a.no_raw and os.path.isdir(a.raw): cmd += ['--raw', a.raw]
run('원장 전처리 (오류 줄·오류 날 뺌)', cmd, cwd=HERE)
last = pd.read_csv(LED, usecols=['일자'], dtype=str).일자.max(); last_d = pd.Timestamp(last)
base = a.base or str(pd.Period(last_d, freq='M') - 1)            # 기준월 = 원장 마지막 날이 든 달의 앞 달 (다 찬 달)
cut = str(pd.Period(base, freq='M') + 1)
RES = os.path.join(D, '결과', f'NongClock_자동_기준{base.replace("-", "")}'); R1 = os.path.join(RES, f'결과_기준{base.replace("-", "")}'); R2 = os.path.join(RES, '데이터'); R3 = os.path.join(RES, '모델입력')
for p in (R1, R2, R3): os.makedirs(p, exist_ok=True)
print(f'  원장 마지막 날 {last} · 기준월 {base}', flush=True)

# 2) 322 단위 일별 가격
run('322 단위 일별 가격', PY + ['n4_일별_단위가격_품종코드정의.py', os.path.join(REF, '새정의_322_품종코드.csv'), UNIT, LED])

F2 = os.path.join(W, 'f2')
if a.mode == 'monthly':
    if not a.base and last_d.day < 3: sys.exit(f'[기다림] 원장 마지막 날이 {last} — 지난달 정산이 다 올라오는 3일 뒤에 돌리세요 (--base 로 강제 가능)')
    run('관측월보 PDF 읽기 (OCR · 생산 전망 추출)', PY + [os.path.join(HERE, 'wolbo_auto.py'), os.path.join(os.path.dirname(os.path.abspath(D)), 'manual', '월보')], cwd=HERE)
    for t in ('tV', 'tW'):
        pin = os.path.join(W, t, '_입력', '01x_품종월_패널_최대확장.csv.gz'); tmp = pin + '.new'
        run(f'월 패널 {t}', PY + [os.path.join(HERE, 'panel_rebuild.py'), LED, REF, t, pin, tmp, base], cwd=HERE); os.replace(tmp, pin)
        run(f'새 자료를 변수에 넣기 {t} (주산지 기상 · 월보 · 통계청)', PY + [os.path.join(HERE, 'feat_update.py'), os.path.join(D, f'자료뿌리_{t}'), os.path.join(W, t), os.path.dirname(os.path.abspath(D)), base, REF, CODE], cwd=HERE)
        run(f'공급 변수 이어 붙이기 {t}', PY + [os.path.join(HERE, 'feat_roll.py'), os.path.join(D, f'자료뿌리_{t}'), base], cwd=HERE)
        run(f'v4 학습·예측 {t}', PY + ['f1_w47_최신기준_C2.py'], env={'NC_NOQ': '1', 'NC_R': os.path.join(D, f'자료뿌리_{t}') + os.sep, 'NC_OUT': os.path.join(W, t), 'NC_FEAT': 'dropsig97', 'NC_CUT': cut}, log=os.path.join(W, f'_log_f1_{t}.txt'))
    run('322 월 예측 (v4 · 따라가기 · 반반)', PY + ['f2_322_최신예측_따라가기.py', os.path.join(W, 'tV'), os.path.join(W, 'tW'), os.path.join(REF, '단위표_v3b_322.csv'), os.path.join(REF, '단위별_모델_출하철_등급.csv'), F2], log=os.path.join(W, '_log_f2.txt'))
    shutil.copy(os.path.join(F2, '01_322_앞으로12달_예측.csv'), os.path.join(R1, f'01_322_월예측_기준{base.replace("-", "")}_앞으로12달.csv'))
    shutil.copy(os.path.join(F2, '02_322_시험예측_2023부터.csv.gz'), os.path.join(R1, '02_322_월예측_시험줄_2023부터.csv.gz'))
    shutil.copy(os.path.join(F2, '03_시험_성적.csv'), os.path.join(R1, '03_월예측_시험성적.csv'))
else:   # daily: 가장 최근 월 예측을 그대로 씀
    got = sorted(glob.glob(os.path.join(D, '결과', 'NongClock_자동_기준*', '결과_기준*', '01_322_월예측_*.csv')))
    src = os.path.dirname(got[-1]) if got else os.path.join(SEED, '결과_기준202610')
    mb = os.path.basename(src).replace('결과_기준', '')
    RES = os.path.join(D, '결과', f'NongClock_자동_기준{mb}'); R1 = os.path.join(RES, f'결과_기준{mb}'); R2 = os.path.join(RES, '데이터'); R3 = os.path.join(RES, '모델입력')
    for p in (R1, R2, R3): os.makedirs(p, exist_ok=True)
    if os.path.abspath(src) != os.path.abspath(R1):
        for f in glob.glob(os.path.join(src, '0[123]_*')): shutil.copy(f, R1)
    base = mb[:4] + '-' + mb[4:]

# 3) 일·주 예측
U7 = os.path.join(W, 'u7'); os.makedirs(U7, exist_ok=True); os.makedirs(os.path.join(W, 'o365'), exist_ok=True); run('일·주 예측 (u7d)', PY + ['u7d_일주_물량뺌.py', U7, UNIT], log=os.path.join(W, '_log_u7.txt'))
bd = last_d.strftime('%Y%m%d')
for f in glob.glob(os.path.join(R1, '05_*')) + glob.glob(os.path.join(R1, '06_*')) + glob.glob(os.path.join(R1, '10_*')): os.remove(f)
for s, t in (('75_최신_일별예측.csv', f'05_일별예측_기준{bd}_1to14거래일.csv'), ('74_최신_주별예측.csv', f'06_주별예측_기준{bd}_1to4주.csv'), ('72_일별_성적.csv', '07_일별_시험성적.csv'), ('71_주별_성적.csv', '08_주별_시험성적.csv'), ('73_단위별_일주성적.csv', '09_단위별_일주_시험성적.csv')):
    shutil.copy(os.path.join(U7, s), os.path.join(R1, t))

# 4) 365일 일별 (e1b 는 옛 묶음 파일 이름을 읽으므로 그 이름으로 임시 폴더를 만든다)
K = os.path.join(W, 'K365'); shutil.rmtree(K, ignore_errors=True); os.makedirs(os.path.join(K, '데이터')); os.makedirs(os.path.join(K, '결과_기준202610'))
u = pd.read_csv(UNIT, parse_dates=['date']); u = u.rename(columns={'단위': '예측단위', 'p': '단가_원kg'})
u[['date', '예측단위', '단가_원kg']].to_csv(os.path.join(K, '데이터', '02_322단위_일별가격_20200101_20261110.csv.gz'), index=False, compression='gzip')
mm = u.assign(연월=u.date.dt.strftime('%Y-%m')).groupby(['예측단위', '연월'])[['국산_kg', '국산금액_원']].sum().reset_index(); mm['단가_원kg'] = mm.국산금액_원 / mm.국산_kg.where(mm.국산_kg > 0)
mm[['예측단위', '연월', '단가_원kg']].to_csv(os.path.join(K, '데이터', '03_322단위_월가격_모델패널_201801_202610.csv.gz'), index=False, compression='gzip')
shutil.copy(os.path.join(REF, '단위별_모델_출하철_등급.csv'), os.path.join(K, '데이터', '05_322단위표_모델계열_부모_모델_출하철.csv'))
shutil.copy(glob.glob(os.path.join(R1, '02_322_월예측_시험줄_*'))[0], os.path.join(K, '결과_기준202610', '02_322_월예측_시험줄_2023부터.csv.gz'))
shutil.copy(glob.glob(os.path.join(R1, '01_322_월예측_*'))[0], os.path.join(K, '결과_기준202610', '01_322_월예측_기준202610_앞으로12달.csv'))
shutil.copy(os.path.join(R1, f'05_일별예측_기준{bd}_1to14거래일.csv'), os.path.join(K, '결과_기준202610', '05_일별예측_기준20261110_1to14거래일.csv'))
O365 = os.path.join(W, 'o365'); run('365일 일별 예측', PY + ['e1b_365일_일별예측.py', K, O365], log=os.path.join(W, '_log_365.txt'))
shutil.copy(glob.glob(os.path.join(O365, '01_322_365일_일별예측_기준*.csv.gz'))[0], os.path.join(R1, f'10_322_365일_일별예측_기준{bd}.csv.gz'))
shutil.copy(os.path.join(O365, '02_365일_일별_시험성적.csv'), os.path.join(R1, '11_365일_일별_시험성적.csv'))

# 5) 묶음의 나머지 (db/make_db_csv.py 가 읽는 것)
shutil.copy(os.path.join(REF, '새정의_322_품종코드.csv'), os.path.join(R2, '01_새정의_322단위_품종코드_달.csv'))
for f in glob.glob(os.path.join(R2, '04_322단위_일별가격_*')): os.remove(f)
shutil.copy(UNIT, os.path.join(R2, f'04_322단위_일별가격_20200101_{bd}.csv.gz'))
shutil.copy(os.path.join(REF, '단위별_모델_출하철_등급.csv'), os.path.join(R2, '05_단위별_모델_출하철_등급.csv'))
for t in ('tV', 'tW'):
    os.makedirs(os.path.join(R3, t, '_입력'), exist_ok=True); shutil.copy(os.path.join(W, t, '_입력', '01x_품종월_패널_최대확장.csv.gz'), os.path.join(R3, t, '_입력'))
open(os.path.join(D, '결과', '_최신.txt'), 'w', encoding='utf-8').write(RES)
print(f'끝: {RES}\n  월 기준 {base} · 일·주 기준일 {last}', flush=True)

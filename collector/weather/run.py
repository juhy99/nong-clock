#!/usr/bin/env python3
"""날씨 수집·전처리 실행기 (리눅스 서버용)

  python run.py collect                        # 5개 수집기 전부
  python run.py collect --only fcst            # 단기·중기예보만 (3시간마다)
  python run.py collect --only asos,aws,agri,longrange
  python run.py collect --backfill             # 처음 1번: 과거 전체 받기 (ASOS 2015~, AWS 1997~, 농업기상 2015-01~)
  python run.py preprocess                     # 기상 통합 전처리 → 날씨 대통합 일별
  python run.py all [--only ...]               # collect 다음 preprocess

- 데이터 폴더: 환경변수 DATA_DIR (기본: 이 폴더의 ./data)
- 인증키: 환경변수 KMA_APIHUB_KEY, DATA_GO_KR_KEY (이 폴더의 .env 파일도 읽음, 이미 있는 환경변수가 우선)
- 수집 기록: data/collect_log.json (최근 100번), 전처리 기록: data/preprocess_log.json
- 실행 화면 전체: data/logs/<시각>_<이름>.log (30일 지나면 지움)
- 인증 오류(종료코드 3)가 나면 data/STOP_<키이름> 파일을 만들고, 그 파일이 있는 동안 그 키를 쓰는 수집은 건너뜀.
  키·활용신청을 고친 뒤 파일을 지우면 다음 실행부터 다시 수집함.
"""
import argparse
import datetime as dt
import fcntl
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
KST = dt.timezone(dt.timedelta(hours=9))
PY = sys.executable

# 이름: (스크립트, 키 이름, 예전 키 이름들, 제한시간 초)
SOURCES = {
    'asos': ('collect_asos.py', 'KMA_APIHUB_KEY', ('KMA_AUTH_KEY',), 4 * 3600),
    'aws': ('collect_aws.py', 'KMA_APIHUB_KEY', ('KMA_AUTH_KEY',), 3 * 3600),
    'agri': ('collect_agri.py', 'DATA_GO_KR_KEY', (), 3 * 3600),
    'fcst': ('collect_fcst.py', 'DATA_GO_KR_KEY', (), 2 * 3600),
    'longrange': ('collect_longrange.py', None, (), 1 * 3600),
}
EXIT_NOKEY, EXIT_AUTH, EXIT_QUOTA = 2, 3, 4
KEEP_RUNS = 100
LOCK_WAIT = int(os.getenv('RUN_LOCK_WAIT', '1800'))   # 같은 수집기가 이미 돌고 있으면 최대 이만큼(초) 기다림


def now():
    return dt.datetime.now(KST)


def load_env():
    """이 폴더의 .env (KEY=VALUE) 읽기. 이미 있는 환경변수는 덮어쓰지 않음."""
    f = HERE / '.env'
    if not f.exists():
        return
    for line in f.read_text(encoding='utf-8-sig').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        k, v = k.strip().removeprefix('export ').strip(), v.strip().strip('"').strip("'")
        if k and v and not os.environ.get(k):
            os.environ[k] = v


def data_dir():
    p = Path(os.getenv('DATA_DIR') or 'data')
    return (p if p.is_absolute() else HERE / p).resolve()


def write_json(path, obj):
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding='utf-8')
    os.replace(tmp, path)


def append_log(path, run):
    # 예보(3시간마다)와 관측(매일)이 같이 돌다 동시에 끝나도 기록이 덮어써지지 않게 잠금 (서버 scheduler.py 는 둘을 따로 실행)
    with Lock('log', wait=120):
        try:
            runs = json.loads(path.read_text(encoding='utf-8')).get('runs', []) if path.exists() else []
        except (ValueError, OSError):
            bad = path.with_name(path.name + f'.깨짐_{now():%Y%m%d_%H%M%S}')
            shutil.copy2(path, bad)                     # 깨진 기록은 옮겨 두고 새로 시작
            runs = []
        runs = (runs + [run])[-KEEP_RUNS:]
        write_json(path, {'runs': runs})


class Lock:
    """fcntl.flock 잠금: 프로세스가 죽으면 OS가 풀어 주므로 남는 잠금이 없음."""
    def __init__(self, name, wait=LOCK_WAIT):
        d = data_dir() / '.locks'
        d.mkdir(parents=True, exist_ok=True)
        self.path, self.wait, self.f = d / f'{name}.lock', wait, None

    def __enter__(self):
        self.f = open(self.path, 'w')
        t0 = time.time()
        while True:
            try:
                fcntl.flock(self.f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self
            except BlockingIOError:
                if time.time() - t0 > self.wait:
                    self.f.close()
                    raise TimeoutError(f'{self.path.stem}: 이전 실행이 {self.wait}초 넘게 계속 중이라 이번엔 건너뜀')
                time.sleep(10)

    def __exit__(self, *exc):
        fcntl.flock(self.f, fcntl.LOCK_UN)
        self.f.close()
        return False


def prune_logs(logdir, days=30):
    cut = time.time() - days * 86400
    for f in logdir.glob('*.log'):
        try:
            if f.stat().st_mtime < cut:
                f.unlink()
        except OSError:
            pass


def run_script(cmd, logfile, timeout):
    """스크립트 실행 → (종료코드, ##STATS 딕셔너리, 마지막 몇 줄)"""
    env = dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8', TZ='Asia/Seoul', DATA_DIR=str(data_dir()))
    with open(logfile, 'w', encoding='utf-8') as lf:
        lf.write('$ ' + ' '.join(str(c) for c in cmd) + '\n'); lf.flush()
        try:
            p = subprocess.run([PY, '-u', *map(str, cmd)], cwd=HERE, env=env, stdin=subprocess.DEVNULL,
                               stdout=lf, stderr=subprocess.STDOUT, timeout=timeout)
            code = p.returncode
        except subprocess.TimeoutExpired:
            code = None
    text = Path(logfile).read_text(encoding='utf-8', errors='replace')
    stats = {}
    for line in text.splitlines():
        if line.startswith('##STATS '):
            try:
                stats = json.loads(line[8:])
            except ValueError:
                pass
    tail = [ln for ln in text.splitlines() if ln.strip() and not ln.startswith('##STATS')][-3:]
    return code, stats, tail


def collect_args(src, backfill):
    t = now().date()
    yday = t - dt.timedelta(days=1)
    D = data_dir() / 'raw'
    if src == 'asos':      # 시작일은 꼭 2015-01-01 (통합 CSV를 이 기간으로 다시 만듦)
        return ['--start', '2015-01-01', '--end', yday.isoformat(), '--out', D / 'asos']
    if src == 'aws':       # 어제가 속한 연도 (1월 1일엔 작년 마지막 날까지 받도록)
        return ['--start', '1997' if backfill else str(yday.year), '--out', D / 'aws']
    if src == 'agri':      # 지난달 ~ 이번 달
        prev = (t.replace(day=1) - dt.timedelta(days=1)).strftime('%Y-%m')
        return ['--start', '2015-01' if backfill else prev, '--end', t.strftime('%Y-%m'), '--out', D / 'agri']
    if src == 'fcst':      # 최근 24시간 발표분 중 아직 없는 것 전부
        return ['--part', 'all', '--times', 'all', '--data', D / 'fcst']
    if src == 'longrange':
        return ['--part', 'latest', '--output', D / 'longrange']
    raise KeyError(src)


def collect(only, backfill=False):
    D = data_dir(); D.mkdir(parents=True, exist_ok=True)
    logdir = D / 'logs'; logdir.mkdir(exist_ok=True); prune_logs(logdir)
    stamp = now().strftime('%Y%m%d_%H%M%S')
    run = {'started_at': now().isoformat(timespec='seconds'), 'ok': True, 'added': 0, 'calls': 0, 'errors': [], 'sources': {}}
    for src in only:
        script, keyname, aliases, timeout = SOURCES[src]
        info = {'ok': False, 'added': 0, 'calls': 0, 'exit': None, 'errors': []}
        run['sources'][src] = info
        t0 = time.time()
        if keyname:
            flag = D / f'STOP_{keyname}'
            if flag.exists():
                info['skipped'] = f'{flag.name} 있음'
                info['errors'].append(f'{flag.name} 파일이 있어 건너뜀 (키·활용신청 확인 후 파일 삭제): '
                                      + flag.read_text(encoding='utf-8', errors='replace').strip()[:200])
            elif not any(os.getenv(k, '').strip() for k in (keyname, *aliases)):
                info['skipped'] = '키 없음'
                info['errors'].append(f'환경변수 {keyname} 없음 → 건너뜀')
        if 'skipped' not in info:
            lf = logdir / f'{stamp}_{src}.log'
            try:
                with Lock(src):
                    code, stats, tail = run_script([script, *collect_args(src, backfill)], lf, timeout)
            except TimeoutError as e:
                code, stats, tail = None, {}, [str(e)]
                info['errors'].append(str(e))
            info.update(exit=code, added=int(stats.get('added', 0) or 0), calls=int(stats.get('calls', 0) or 0), log=lf.name)
            info['errors'] += stats.get('errors', [])
            if code is None and not info['errors']:
                info['errors'].append(f'제한시간 {timeout}초 넘어 중단 (다음 실행에서 이어받음)')
            if code == EXIT_AUTH:
                reason = stats.get('auth_error') or ' / '.join(tail)
                flag = D / f'STOP_{keyname}'
                flag.write_text(f'{now().isoformat(timespec="seconds")} {src}: {reason}\n'
                                f'키·활용신청을 고친 뒤 이 파일을 지우면 다음 실행부터 다시 수집합니다.\n', encoding='utf-8')
                info['errors'].append(f'인증 오류 → {flag.name} 만듦: {reason}')
            elif code not in (0, None) and not info['errors']:
                info['errors'].append(f'종료코드 {code}: ' + ' / '.join(tail)[:300])
            info['ok'] = code == 0 and not info['errors']
        info['seconds'] = round(time.time() - t0, 1)
        run['added'] += info['added']; run['calls'] += info['calls']
        run['errors'] += [f'{src}: {e}' for e in dict.fromkeys(info['errors'])]
        run['ok'] = run['ok'] and info['ok']
        print(f"[{src}] {'정상' if info['ok'] else '문제'} | 호출 {info['calls']} | 추가 {info['added']} | "
              f"{info['seconds']}초" + (f" | {info['errors'][0][:150]}" if info['errors'] else ''), flush=True)
    run = {'finished_at': now().isoformat(timespec='seconds'), **run}
    append_log(D / 'collect_log.json', run)
    return run['ok']


# ───────────── 전처리 ─────────────
def copy_new(src, dst):
    """src가 dst보다 새것이거나 크기가 다르면 복사. 새 파일이 예전보다 1% 넘게 작으면 멈춤(원본 일부만 남은 사고 방지)."""
    src, dst = Path(src), Path(dst)
    if not src.exists():
        return 0
    if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime and dst.stat().st_size == src.stat().st_size:
        return 0
    if dst.exists() and dst.stat().st_size > 100_000 and src.stat().st_size < 0.99 * dst.stat().st_size:
        raise RuntimeError(f'{src.name}: 새 파일({src.stat().st_size:,}B)이 예전({dst.stat().st_size:,}B)보다 작아 덮어쓰지 않음 → 원본 확인')
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.name + '.tmp')
    shutil.copy2(src, tmp)
    os.replace(tmp, dst)
    return 1


def preprocess():
    D = data_dir(); R = D / 'raw'
    base, link, site = D / 'integrated', D / 'link', D / 'site'
    logdir = D / 'logs'; logdir.mkdir(parents=True, exist_ok=True)
    stamp = now().strftime('%Y%m%d_%H%M%S')
    run = {'started_at': now().isoformat(timespec='seconds'), 'ok': False, 'added': 0, 'calls': 0, 'errors': [], 'steps': {}}
    out_csv = site / '날씨_대통합_일별.csv'
    rows = lambda p: max(0, sum(1 for _ in open(p, 'rb')) - 1) if p.exists() else 0
    before = rows(out_csv)
    try:
        with Lock('preprocess'):
            # 1) 수집 결과를 기상 통합 01_원본으로 복사 (전처리갱신.py s_weather와 같은 파일)
            with Lock('asos'), Lock('aws'), Lock('agri'):
                o = base / '01_원본'
                n = copy_new(R / 'asos' / 'ASOS_일자료_전국통합.csv', o / 'ASOS' / 'ASOS_일자료_2015_2026_API.csv')
                n += copy_new(R / 'asos' / '관측소' / '지점정보_원본.txt', o / 'ASOS' / '지점정보_원본.txt')
                for f in sorted((R / 'aws' / '원본').glob('*.txt.gz')):
                    n += copy_new(f, o / 'AWS' / '원본' / f.name)
                n += copy_new(R / 'agri' / '농업기상_일자료_통합.csv', o / '농업기상' / '농업기상_일자료_통합.csv')
                n += copy_new(R / 'agri' / '관측지점_목록.csv', o / '농업기상' / '관측지점_목록.csv')
            run['steps']['복사'] = f'새 원본 {n}개'
            print(f'[전처리] 01_원본에 새 원본 {n}개 복사', flush=True)
            # 2) 연도 캐시 지우기: 올해(1월엔 작년도) — 지우지 않으면 새 날짜가 반영 안 됨
            t = now().date()
            ys = {t.year} | ({t.year - 1} if t.month == 1 else set())
            gone = 0
            for y in ys:
                for c in (base / '02_전처리' / 'AWS' / f'{y}.csv', base / '02_전처리' / 'AWS' / '_좌표' / f'{y}.csv',
                          link / '_집계' / f'{y}_stat.json', site / '_중간' / f'sgg_{y}.csv'):
                    if c.exists():
                        c.unlink(); gone += 1
            run['steps']['캐시삭제'] = f'{sorted(ys)}년 {gone}개'
            # 3) 기상 통합 전처리 → 4) 날씨 대통합 일별
            for name, cmd in (('기상통합', ['preprocess_weather.py', '--base', base, '--link', link, '--step', 'all']),
                              ('대통합일별', ['build_weather_daily.py', '--link', link, '--out', site])):
                lf = logdir / f'{stamp}_전처리_{name}.log'
                code, _, tail = run_script(cmd, lf, 6 * 3600)
                run['steps'][name] = {'exit': code, 'log': lf.name}
                print(f'[전처리] {name}: 종료코드 {code}', flush=True)
                if code != 0:
                    raise RuntimeError(f'{name} 실패(종료코드 {code}): ' + ' / '.join(tail)[:300])
        run['ok'] = True
    except Exception as e:
        run['errors'].append(str(e)[:500])
        print(f'[전처리] 오류: {e}', flush=True)
    run['added'] = rows(out_csv) - before          # 날씨_대통합_일별.csv 행 수 증가분
    append_log(D / 'preprocess_log.json', {'finished_at': now().isoformat(timespec='seconds'), **run})
    return run['ok']


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['collect', 'preprocess', 'all'])
    ap.add_argument('--only', default='', help='쉼표로: asos,aws,agri,fcst,longrange (기본: 전부)')
    ap.add_argument('--backfill', action='store_true', help='처음 1번: 과거 전체 기간 받기')
    a = ap.parse_args()
    load_env()
    only = [s.strip() for s in a.only.split(',') if s.strip()] or list(SOURCES)
    bad = [s for s in only if s not in SOURCES]
    if bad:
        ap.error('없는 이름: ' + ', '.join(bad))
    ok = True
    if a.cmd in ('collect', 'all'):
        ok = collect(only, a.backfill) and ok
    if a.cmd in ('preprocess', 'all'):
        ok = preprocess() and ok
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()

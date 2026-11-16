# -*- coding: utf-8 -*-
"""이사 꾸러미 만들기 (11-16): 학원 PC 를 다시 안 써도 집·서버에서 지금과 똑같이 돌리게 필요한 것을 한 폴더에 모음.
  py -3 -X utf8 scripts/이사_꾸러미.py [꾸러미 폴더]      (기본 D:\\nong-clock-data\\_이사_꾸러미_YYYYMMDD)
담는 것
  1 코드\\nong-clock.bundle      git 의 모든 브랜치·커밋 (push 안 한 커밋 포함)
  2 코드\\커밋안된_파일.zip      아직 커밋 안 한 파일 + git 에 안 넣는 큰 파일(v4 seed · OCR 글꼴). .env 는 넣지 않음
  3 DB\\farmdb.dump              도커 DB 전체 (회원·게시판·시세·예측). Docker 의 nong-clock-db 가 켜져 있어야 함
  4 자료\\05_DB적재\\data         원자료·표·모델 결과(v4 포함)·날씨
  5 분석\\nong-clock-ml           분석 노트북
  00_집에서_복원하는_법.md
인증키(.env)는 넣지 않음 — 직접 USB 등으로 옮기기 (꾸러미를 클라우드에 올려도 키가 새지 않게)
"""
import datetime as dt, hashlib, os, shutil, subprocess, sys, zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA_ROOT = Path(os.getenv('NC_DATA_ROOT') or (r'D:\nong-clock-data' if Path(r'D:\nong-clock-data').exists() else r'C:\finalproject\nong-clock-data'))
DATA = DATA_ROOT / '05_DB적재' / 'data'
ML = Path(r'C:\Users\M\Desktop\test\nong-clock-ml')
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else DATA_ROOT / f'_이사_꾸러미_{dt.date.today():%Y%m%d}'
# 커밋 안 해도 꼭 가져갈 것 (git status 의 변경·새 파일 + 아래 무시 파일)
EXTRA = ['collector/daily/model/seed', 'collector/daily/tools/tessdata']
SKIP_NAMES = {'.env', '__pycache__', 'node_modules', 'build', '.gradle'}

def step(t): print(f'\n▶ {t}', flush=True)
def fail(t): print(f'[멈춤] {t}'); sys.exit(1)
def size(p): return sum(f.stat().st_size for f in Path(p).rglob('*') if f.is_file()) if Path(p).is_dir() else Path(p).stat().st_size
def gb(n): return f'{n / 1024**3:.2f}GB' if n > 1024**3 else f'{n / 1024**2:.1f}MB'

if OUT.exists() and any(OUT.iterdir()): fail(f'{OUT} 가 이미 있어요. 지우거나 다른 폴더 이름을 주세요')
(OUT / '코드').mkdir(parents=True, exist_ok=True); (OUT / 'DB').mkdir(exist_ok=True)
print(f'꾸러미 폴더: {OUT}')

step('1 코드: git 모든 브랜치·커밋')
b = OUT / '코드' / 'nong-clock.bundle'
r = subprocess.run(['git', '-C', str(REPO), 'bundle', 'create', str(b), '--all'], capture_output=True, text=True, encoding='utf-8', errors='replace')
if r.returncode: fail('git bundle 실패\n' + r.stderr)
r = subprocess.run(['git', '-C', str(REPO), 'bundle', 'verify', str(b)], capture_output=True, text=True, encoding='utf-8', errors='replace')
if r.returncode: fail('git bundle 확인 실패\n' + r.stderr)
br = subprocess.run(['git', '-C', str(REPO), 'branch', '--show-current'], capture_output=True, text=True).stdout.strip()
head = subprocess.run(['git', '-C', str(REPO), 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True).stdout.strip()
print(f'   {gb(size(b))} · 지금 브랜치 {br} ({head})')

step('2 코드: 커밋 안 한 파일 + 큰 파일')
st = subprocess.run(['git', '-C', str(REPO), 'status', '--porcelain', '-z', '--untracked-files=all'], capture_output=True).stdout.decode('utf-8').split('\0')
paths = []
for e in st:
    if len(e) > 3 and e[:2] != ' D' and e[:2] != 'D ':
        paths.append(e[3:])
paths = [p for p in paths if p != 'frontend/package-lock.json']   # npm install 이 바꾼 것 — 안 가져감
z = OUT / '코드' / '커밋안된_파일.zip'; n = 0
with zipfile.ZipFile(z, 'w', zipfile.ZIP_DEFLATED) as zf:
    for p in paths + EXTRA:
        src = REPO / p
        files = [src] if src.is_file() else [f for f in src.rglob('*') if f.is_file()] if src.is_dir() else []
        for f in files:
            rel = f.relative_to(REPO)
            if any(part in SKIP_NAMES for part in rel.parts) or f.name.startswith('.env'): continue
            zf.write(f, rel.as_posix()); n += 1
print(f'   파일 {n}개 · {gb(size(z))}')

step('3 DB: 도커 nong-clock-db 전체 백업 (pg_dump)')
d = OUT / 'DB' / 'farmdb.dump'
with open(d, 'wb') as f:
    r = subprocess.run(['docker', 'exec', 'nong-clock-db', 'pg_dump', '-U', 'postgres', '-Fc', 'farmdb'], stdout=f, stderr=subprocess.PIPE)
if r.returncode or size(d) < 1024 * 1024: fail('DB 백업 실패 — Docker Desktop 과 nong-clock-db 가 켜져 있는지 확인 (docker compose up -d db)\n' + r.stderr.decode('utf-8', 'replace'))
r = subprocess.run(['docker', 'exec', 'nong-clock-db', 'psql', '-U', 'postgres', '-d', 'farmdb', '-At', '-c',
                    "SELECT 'price_unit_daily '||count(*)||' 줄, 마지막 '||max(date) FROM price_unit_daily UNION ALL SELECT 'price_forecast_daily 기준일 '||count(DISTINCT base_date)||'개, 마지막 '||max(base_date) FROM price_forecast_daily UNION ALL SELECT 'users '||count(*) FROM users"],
                   capture_output=True, text=True, encoding='utf-8', errors='replace')
print(f'   {gb(size(d))}'); print('   ' + (r.stdout.strip().replace('\n', '\n   ') or r.stderr.strip()))
(OUT / 'DB' / 'DB_내용.txt').write_text(r.stdout, encoding='utf-8')

step(f'4 자료: {DATA} (몇 분 걸림)')
if not DATA.exists(): fail(f'자료 폴더가 없어요: {DATA}')
shutil.copytree(DATA, OUT / '자료' / '05_DB적재' / 'data', ignore=shutil.ignore_patterns('.locks', '*.lock', '.env*'))
print(f'   {gb(size(OUT / "자료"))}')

step(f'5 분석 노트북: {ML}')
if ML.exists():
    shutil.copytree(ML, OUT / '분석' / 'nong-clock-ml', ignore=shutil.ignore_patterns('.ipynb_checkpoints', '__pycache__', '.env*'))
    print(f'   {gb(size(OUT / "분석"))}')
else:
    print('   없음 — 건너뜀')

envs = [str(p.relative_to(REPO)) for p in [REPO / '.env', REPO / 'frontend' / '.env', REPO / 'collector' / 'daily' / '.env'] if p.exists()]
(OUT / '00_집에서_복원하는_법.md').write_text(f"""# 농클락 이사 꾸러미 ({dt.datetime.now():%Y-%m-%d %H:%M}, 학원 PC 에서 만듦)

학원 PC 브랜치: `{br}` ({head})

## 꾸러미에 없는 것 — 직접 옮기기
- 인증키 파일 (USB 로만, 클라우드·카톡에 올리지 않기): {', '.join(envs) or '없음'}
- D:\\nong-clock-data 의 다른 분석 폴더(01~42번 등)는 안 넣었어요. 필요하면 폴더째 외장 하드로

## 집(또는 서버)에서 복원 순서
1. 코드
   - 처음이면: `git clone 코드\\nong-clock.bundle nong-clock` → `cd nong-clock` → `git checkout {br}` → `git remote set-url origin https://github.com/juhy99/nong-clock`
   - 이미 저장소가 있으면: `git fetch <꾸러미>\\코드\\nong-clock.bundle "refs/heads/*:refs/remotes/학원/*"` → `git checkout -B {br} 학원/{br}`
   - `코드\\커밋안된_파일.zip` 을 저장소 맨 위 폴더에 풀기 (같은 이름은 덮어쓰기)
   - 인증키 파일을 같은 자리에 넣기
2. 자료: `자료\\05_DB적재` 를 `C:\\finalproject\\nong-clock-data\\` 안에 넣기 (bat 들이 이 경로를 자동으로 찾음. 다른 곳이면 환경 변수 NC_DATA_ROOT)
3. DB
   ```
   docker compose up -d db
   docker exec -i nong-clock-db pg_restore -U postgres -d farmdb --clean --if-exists --no-owner < DB\\farmdb.dump
   docker compose up -d --build
   ```
   (cmd 에서. PowerShell 이면 `cmd /c "docker exec -i ... < DB\\farmdb.dump"`)
4. 확인: `DB\\DB_내용.txt` 와 같은 숫자가 나오는지
   `docker exec nong-clock-db psql -U postgres -d farmdb -c "SELECT max(date) FROM price_unit_daily"`
5. 파이썬: `py -3 -m pip install -r collector\\daily\\requirements.txt lightgbm==4.7.0 scikit-learn==1.9.1 scipy`
6. 시험: `scripts\\v4_맞춰보기.bat` → "결과: 같음" · `scripts\\매일_예측_갱신.bat`
""", encoding='utf-8')

step('끝')
print(f'꾸러미: {OUT}  ({gb(size(OUT))})')
print('이 폴더를 통째로 외장 하드·USB·구글 드라이브로 옮기세요. 인증키(.env)는 따로!')

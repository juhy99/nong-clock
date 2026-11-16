# -*- coding: utf-8 -*-
"""관측월보 PDF → (필요하면 OCR) → 생산 전망 전년비 자동 추출. 2026-11-13
 사람이 할 일: KREI 에서 받은 월보 PDF(또는 ZIP)를 data/manual/월보/ 에 넣기만 하면 된다. 숫자를 적을 필요 없음.
 대상: 엽근채소(VC…)·양념채소(VS…)·감자(VPO…)·과일(F…) 월보. 다른 분야는 건너뜀
 순서 (예전 전처리와 같은 방법):
  1) 글자 뽑기: pdftotext. 본문이 윤곽선 글자라 글자가 거의 안 나오면 전 쪽 OCR (pdftoppm 200dpi 회색 → tesseract kor, 월보_전처리.py 와 같은 설정)
  2) 채소: 35번 build_wb_croptype.py(불릿, 2021~) + build_wb_croptype_old.py(문장) → 불릿 우선으로 합침 = 월보_작형별_수급지표_35_05 와 같은 모양
     과일: 70번 w12a(표·문장·착과 신호) → 월보_과일5_생산_재추출 과 같은 모양
     (세 코드는 원래 것 그대로. 지금 페이지 텍스트로 다시 돌리면 4,771줄 · 1,137줄이 예전 파일과 100% 같음)
  3) 결과를 data/manual/월보/_처리/월보_자동_작형.csv · 월보_자동_과일.csv 로 → model/feat_update.py 가 월보 신호(83)에 넣음
 사용: python wolbo_auto.py <월보 폴더> [--tessdata <폴더>] [--시간제한 초]"""
import argparse, csv, glob, hashlib, json, os, re, shutil, subprocess, sys, tempfile, time, zipfile
from concurrent.futures import ThreadPoolExecutor
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__)); CODE = os.path.join(HERE, 'code', '월보')
PRE = [('VPO', '감자'), ('VC', '엽근채소'), ('VS', '양념채소'), ('F', '과일')]          # 파일 이름 앞 글자 (긴 것 먼저) — FV(과채)는 제외
KOR = [('엽근채소', '엽근채소'), ('양념채소', '양념채소'), ('감자', '감자'), ('과일', '과일')]
CTRL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f\u200b-\u200f\ufeff\ufffd]")
csv.field_size_limit(2**31 - 1)

def clean(t):   # 월보_전처리.py 와 같음
    t = CTRL.sub('', t.replace('\u00a0', ' '))
    t = re.sub(r'[ \t]+\n', '\n', t)
    return re.sub(r'\n{3,}', '\n\n', t).strip()

def tool(name):
    """윈도에서 PATH 에 없을 때 흔한 설치 위치를 찾음"""
    p = shutil.which(name)
    if p: return p
    if os.name == 'nt':
        cands = [rf'C:\Program Files\Tesseract-OCR\{name}.exe', rf'C:\Program Files (x86)\Tesseract-OCR\{name}.exe']
        la = os.environ.get('LOCALAPPDATA', '')
        cands += glob.glob(os.path.join(la, 'Microsoft', 'WinGet', 'Packages', 'oschwartz10612.Poppler*', '*', 'Library', 'bin', f'{name}.exe'))
        cands += glob.glob(rf'C:\Program Files\poppler*\Library\bin\{name}.exe') + glob.glob(rf'C:\Program Files\poppler*\bin\{name}.exe')
        for c in cands:
            if os.path.exists(c): return c
    return None

def run(cmd, timeout=600):
    return subprocess.run(cmd, capture_output=True, timeout=timeout).stdout.decode('utf-8', 'ignore')

def pdftext(pdf):
    rp = [clean(x) for x in run([tool('pdftotext'), '-q', '-enc', 'UTF-8', pdf, '-'], 300).split('\f')]
    while rp and not rp[-1]: rp.pop()
    return rp

def npages(pdf):
    m = re.search(r'Pages:\s*(\d+)', run([tool('pdfinfo'), pdf], 60)); return int(m.group(1)) if m else 0

def ocr_pages(pdf, n, cache, td):
    os.makedirs(cache, exist_ok=True); env = dict(os.environ, OMP_THREAD_LIMIT='1'); tmp = tempfile.mkdtemp()
    def one(i):
        cp = os.path.join(cache, f'p{i:03d}.txt')
        if os.path.exists(cp): return open(cp, encoding='utf-8').read()
        stem = os.path.join(tmp, f'pg{i}')
        subprocess.run([tool('pdftoppm'), '-q', '-r', '200', '-gray', '-png', '-f', str(i), '-l', str(i), '-singlefile', pdf, stem], check=True, timeout=300)
        cmd = [tool('tesseract'), stem + '.png', 'stdout', '-l', 'kor+eng', '--psm', '3', '-c', 'preserve_interword_spaces=1'] + (['--tessdata-dir', td] if td else [])
        t = clean(subprocess.run(cmd, capture_output=True, timeout=600, env=env).stdout.decode('utf-8', 'ignore'))
        os.remove(stem + '.png'); open(cp + '.tmp', 'w', encoding='utf-8').write(t); os.replace(cp + '.tmp', cp); return t
    with ThreadPoolExecutor(max(1, os.cpu_count() or 1)) as ex: return list(ex.map(one, range(1, n + 1)))

def classify(name, first_text):
    b = os.path.basename(name); stem = re.sub(r'\.pdf$', '', b, flags=re.I)
    m = re.match(r'([A-Za-z]+)\d', stem); bun = None
    if m:
        bun = next((v for k, v in PRE if m.group(1).upper() == k), None)
    if bun is None:
        bun = next((v for k, v in KOR if k in b), None) or next((v for k, v in KOR if k in first_text[:400]), None)
    y = mo = None
    g = re.search(r'(20\d{2})(\d{2})', stem)
    if g and 1 <= int(g.group(2)) <= 12: y, mo = int(g.group(1)), int(g.group(2))
    c = re.search(r'(20\d{2})\s*년\s*(\d{1,2})\s*월\s*호', first_text[:3000])         # 표지 'YYYY년 M월호' 우선 (월보_다시추출.py 와 같음)
    if c and 1 <= int(c.group(2)) <= 12: y, mo = int(c.group(1)), int(c.group(2))
    return bun, y, mo

def collect_pdfs(src, tmp):
    out = []
    for p in sorted(glob.glob(os.path.join(src, '**', '*'), recursive=True)):
        if os.sep + '_처리' + os.sep in p or not os.path.isfile(p): continue
        if p.lower().endswith('.pdf'): out.append((p, os.path.basename(p), open(p, 'rb').read()))
        elif p.lower().endswith('.zip'):
            try: z = zipfile.ZipFile(p)
            except zipfile.BadZipFile: print(f'  ✗ ZIP 손상: {os.path.basename(p)}'); continue
            for i in z.infolist():
                n = i.filename
                if not i.flag_bits & 0x800:
                    try: n = n.encode('cp437').decode('cp949')
                    except Exception: pass
                if n.lower().endswith('.pdf'): out.append((p, os.path.basename(n), z.read(i)))
    return out

def extract(pages_dir, out_dir):
    """원래 추출 코드 3개를 그대로 돌림 → 작형(05 모양) · 과일(w12a 모양)"""
    os.makedirs(out_dir, exist_ok=True); PY = [sys.executable, '-X', 'utf8']; res = {}
    has = lambda b: os.path.exists(os.path.join(pages_dir, f'{b}_페이지텍스트.csv'))
    if any(has(b) for b in ('엽근채소', '양념채소', '감자')):
        for s in ('build_wb_croptype.py', 'build_wb_croptype_old.py'):
            r = subprocess.run(PY + [os.path.join(CODE, s), pages_dir, out_dir], capture_output=True, text=True, encoding='utf-8', errors='replace')
            if r.returncode != 0: raise SystemExit(f'[월보 추출 실패] {s}: ' + (r.stderr or r.stdout).strip().splitlines()[-1])
        M = {'재배(의향)면적': 'area', '재배면적': 'area', '단수': 'yld', '생산량': 'prod', '출하량': 'prod', '저장량': 'store', '재고량': 'store'}
        b = pd.read_csv(os.path.join(out_dir, '02_품목_작형_지표_발행월_전년비.csv')); o = pd.read_csv(os.path.join(out_dir, '04_옛호_품목_작형_지표_발행월_전년비.csv'))
        b['지표'] = b.지표.map(M); b = b.dropna(subset=['지표']).groupby(['품목', '작형', '지표', '발행']).전년비_pct.median().reset_index(); b['출처'] = '불릿(2021~)'
        W = pd.concat([b, o.assign(출처='문장')]).drop_duplicates(['품목', '작형', '지표', '발행'], keep='first')
        res['작형'] = W[['품목', '작형', '지표', '발행', '전년비_pct', '출처']]
    if has('과일'):
        f = os.path.join(out_dir, 'w12a.csv')
        r = subprocess.run(PY + [os.path.join(CODE, 'w12a_월보_생산전망_재추출_표문장신호.py'), os.path.join(pages_dir, '과일_페이지텍스트.csv'), f], capture_output=True, text=True, encoding='utf-8', errors='replace')
        if r.returncode != 0: raise SystemExit('[월보 추출 실패] w12a: ' + (r.stderr or r.stdout).strip().splitlines()[-1])
        res['과일'] = pd.read_csv(f)
    return res

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('src'); ap.add_argument('--tessdata'); ap.add_argument('--시간제한', type=int, default=3600)
    a = ap.parse_args(); src = a.src; os.makedirs(src, exist_ok=True); W = os.path.join(src, '_처리'); os.makedirs(W, exist_ok=True); t0 = time.time()
    st_f = os.path.join(W, '처리기록.json'); st = json.load(open(st_f, encoding='utf-8')) if os.path.exists(st_f) else {}
    td = a.tessdata or os.path.join(os.path.dirname(HERE), 'tools', 'tessdata')
    td = td if os.path.exists(os.path.join(td, 'kor.traineddata')) else None
    tmp = tempfile.mkdtemp(); new = 0
    for origin, name, data in collect_pdfs(src, tmp):
        h = hashlib.sha1(data).hexdigest()
        if h in st: continue
        if time.time() - t0 > a.시간제한: print('  시간 제한 — 다음 실행 때 이어서'); break
        pdf = os.path.join(tmp, 'x.pdf'); open(pdf, 'wb').write(data)
        miss = [t for t in ('pdftotext', 'pdfinfo', 'pdftoppm') if not tool(t)]
        if miss: raise SystemExit(f'[없음] Poppler({", ".join(miss)}) — 0_설치.bat 을 다시 돌리세요 (winget install oschwartz10612.Poppler)')
        raw = pdftext(pdf); n = npages(pdf) or len(raw); chars = sum(map(len, raw)); kb = len(data) / 1024
        bun, y, mo = classify(name, raw[0] if raw else '')
        if bun is None or y is None:
            st[h] = {'파일': name, '상태': '건너뜀(분야·발행월 모름)' if bun is None or y is None else ''}; print(f'  · {name}: 분야나 발행월을 몰라 건너뜀'); continue
        if bun not in ('엽근채소', '양념채소', '감자', '과일'):
            st[h] = {'파일': name, '상태': f'건너뜀({bun})'}; continue
        need = chars <= 200 * max(n, 1) * 0.3 or (kb > 300 and chars / max(n, 1) < 150) or (kb > 1024 and chars < 1000)
        how = '텍스트'
        if need:
            if not tool('tesseract'): raise SystemExit('[없음] Tesseract — 0_설치.bat 을 다시 돌리세요 (winget install UB-Mannheim.TesseractOCR)')
            if not td: raise SystemExit('[없음] tools/tessdata/kor.traineddata (한국어 OCR 자료) — 폴더를 통째로 다시 복사하세요')
            raw = ocr_pages(pdf, n, os.path.join(W, 'ocr_cache', f'{bun}_{y}{mo:02d}_{h[:8]}'), td); how = 'OCR'
            b2, y2, m2 = classify(name, raw[0] if raw else '')
            if y2: y, mo = y2, m2
        pg = os.path.join(W, '페이지텍스트'); os.makedirs(pg, exist_ok=True); f = os.path.join(pg, f'{bun}_페이지텍스트.csv')
        old = pd.read_csv(f, dtype={'텍스트': str}) if os.path.exists(f) else pd.DataFrame(columns=['분야', '연도', '발행월', '파일', '페이지', '텍스트'])
        old = old[~((old.연도 == y) & (old.발행월 == mo))]                                          # 같은 호를 다시 넣으면 새 것으로
        add = pd.DataFrame([{'분야': bun, '연도': y, '발행월': mo, '파일': name, '페이지': i, '텍스트': t} for i, t in enumerate(raw, 1) if t])
        pd.concat([old, add], ignore_index=True).sort_values(['연도', '발행월', '페이지']).to_csv(f, index=False, encoding='utf-8-sig')
        st[h] = {'파일': name, '분야': bun, '호': f'{y}-{mo:02d}', '쪽': n, '글자': sum(map(len, raw)), '방법': how, '처리': time.strftime('%Y-%m-%d %H:%M')}
        json.dump(st, open(st_f, 'w', encoding='utf-8'), ensure_ascii=False, indent=1); new += 1
        print(f'  ✔ {name}: {bun} {y}-{mo:02d}호 {n}쪽 ({how})', flush=True)
    json.dump(st, open(st_f, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    pg = os.path.join(W, '페이지텍스트')
    if not os.path.isdir(pg): print('월보: 넣은 PDF 없음 (data/manual/월보/ 에 KREI 월보 PDF 를 넣으면 자동으로 읽음)'); return
    res = extract(pg, os.path.join(W, '추출'))
    if '작형' in res: res['작형'].to_csv(os.path.join(W, '월보_자동_작형.csv'), index=False, encoding='utf-8-sig')
    if '과일' in res: res['과일'].to_csv(os.path.join(W, '월보_자동_과일.csv'), index=False, encoding='utf-8-sig')
    hos = sorted({(v.get('분야'), v.get('호')) for v in st.values() if v.get('호')}, key=lambda x: x[1])
    print(f"월보: 새로 읽은 PDF {new} · 지금까지 {len(hos)}개 (분야·호, {hos[0][1] if hos else '-'}~{hos[-1][1] if hos else '-'}) · 채소 작형 지표 {len(res.get('작형', []))}줄 · 과일 {len(res.get('과일', []))}줄")

if __name__ == '__main__':
    main()

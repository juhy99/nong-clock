# -*- coding: utf-8 -*-
"""기상청 장기기상전망(1개월·3개월 전망) 수집기 — 2026-10-21

받는 곳
  - 기상청 날씨누리 1개월 전망(매주 목 11시), 3개월 전망(매월 23일 11시) PDF
    목록 API : https://www.weather.go.kr/w/wnuri-fct/rest/weather/long-term.do?kind={1|3}&stn={지점}
    PDF     : https://www.weather.go.kr/w/repositary/xml/fct/mon/{파일명}
    지점(지역) 11개: 108 전국, 109 서울·인천·경기, 101 강원영서, 105 강원영동, 131 충북,
                     133 대전·세종·충남, 146 전북, 156 광주·전남, 143 대구·경북, 159 부산·울산·경남, 184 제주
    ※ 날씨누리는 '지금 발표된 것'만 올려둠(지난 PDF는 지워짐) → 이 수집기를 매주 돌려 쌓아야 함
  - (선택) 인터넷 아카이브(web.archive.org)에 저장된 과거 PDF (드문드문 있음)

만드는 것
  data/pdf/1개월|3개월/<지점>/fct_mon?_<지점>_<발표일>.pdf  (원본)
  data/text/<파일명>.txt                                  (PDF 글자 그대로)
  data/csv/01_장기전망_지역별_확률.csv   발표일×지역×기간(주/월)×요소(평균기온·강수량)
            평년비슷범위(하·상), 확률(낮음/적음·비슷·높음/많음), 최대확률범주
  data/csv/00_추출_전체.csv              표(전국 PDF)·문장(지역 PDF) 둘 다 (대조용)
  data/csv/02_발표목록.csv               파일별 발표일시·다음발표·전망기간·추출행수·상태
  data/수집로그.csv

원래 파일: collect_longrange.py (리눅스 서버용으로 기본 폴더·안내문만 바꿈). 인증키 없음.
기본 저장 폴더: data/raw/longrange (--output 으로 바꿈)

실행 예
  python collect_longrange.py                  # 최신 받기 + CSV 다시 만들기 (서버: 매일)
  python collect_longrange.py --part wayback   # 아카이브 과거 PDF 받기 + CSV
  python collect_longrange.py --part parse     # 받은 PDF로 CSV만 다시
  python collect_longrange.py --test           # 전국(108)만 시험 → test_data/
필요: pip install pypdf  (truststore·certifi는 선택)
"""
import argparse, csv, datetime as dt, json, os, re, sys, time
import wxcommon  # urlopen 호출 수 세기 — urllib import보다 먼저
import urllib.parse, urllib.request
from itertools import combinations
from pathlib import Path

BASE = 'https://www.weather.go.kr/w/'
LIST_API = BASE + 'wnuri-fct/rest/weather/long-term.do?kind={kind}&stn={stn}'
PDF_URL = BASE + 'repositary/xml/fct/mon/{fn}'
STNS = ['108', '109', '101', '105', '131', '133', '146', '156', '143', '159', '184']
STN_NAME = {'108': '전국', '109': '서울·인천·경기', '101': '강원영서', '105': '강원영동', '131': '충북',
            '133': '대전·세종·충남', '146': '전북', '156': '광주·전남', '143': '대구·경북', '159': '부산·울산·경남',
            '184': '제주', 'NKW': '북한 평안·황해', 'NKE': '북한 함경'}
KIND_NAME = {'1': '1개월', '3': '3개월'}
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36',
      'Referer': 'https://www.weather.go.kr/w/climate/prediction/month1.do'}
WAYBACK_PREFIX = ['www.weather.go.kr/w/repositary/xml/fct/mon/', 'weather.go.kr/w/repositary/xml/fct/mon/',
                  'www.weather.go.kr/repositary/xml/fct/mon/', 'www.kma.go.kr/repositary/xml/fct/mon/',
                  'web.kma.go.kr/repositary/xml/fct/mon/']
FN_RE = re.compile(r'fct_mon([13])_(\d{3})_(cmt_)?(\d{8})\.pdf$')

# ---------------------------------------------------------------- 공통
LOG = []

def log(kind, target, status, note=''):
    LOG.append(dict(시각=dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 작업=kind, 대상=target, 결과=status, 메모=note))
    print(f'[{status}] {kind} {target} {note}', flush=True)


def _ssl_contexts():
    """기본 → truststore(윈도 인증서 저장소) → certifi. 인증서 검증은 끄지 않는다.
    'self-signed certificate in certificate chain'은 보안 프로그램·회사/학교망이 HTTPS를 중간에서
    검사할 때 주로 난다. 그 검사용 인증서는 윈도 저장소에 들어 있어 truststore로 해결되는 경우가 많다."""
    import ssl
    ctxs = [('기본', ssl.create_default_context())]
    try:
        import truststore
        ctxs.append(('truststore', truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)))
    except Exception:
        pass
    try:
        import certifi
        ctxs.append(('certifi', ssl.create_default_context(cafile=certifi.where())))
    except Exception:
        pass
    return ctxs

_CTX_BY_HOST = {}
_TRUSTSTORE_HINT = [False]


def http_get(url, tries=3, timeout=60, sleep=0.6):
    host = urllib.parse.urlsplit(url).hostname or ''
    last = None
    for i in range(tries):
        ctxs = [_CTX_BY_HOST[host]] if host in _CTX_BY_HOST else _ssl_contexts()
        for name, ctx in ctxs:
            try:
                req = urllib.request.Request(url, headers=UA)
                with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
                    data = r.read(); ctype = r.headers.get('Content-Type', '')
                if host not in _CTX_BY_HOST:
                    _CTX_BY_HOST[host] = (name, ctx)
                    if name != '기본':
                        print(f'  ({host}: {name} 인증서로 연결)', flush=True)
                time.sleep(sleep)
                return data, ctype
            except Exception as e:  # noqa
                last = e
                if 'CERTIFICATE_VERIFY_FAILED' in repr(e):
                    continue  # 다음 인증서 저장소로
                break
        if last is not None and 'CERTIFICATE_VERIFY_FAILED' in repr(last):
            if not _TRUSTSTORE_HINT[0]:
                _TRUSTSTORE_HINT[0] = True
                try:
                    import truststore  # noqa
                    print('  ※ 시스템 인증서 저장소로도 확인 실패: 이 서버의 네트워크(프록시/방화벽)가 '
                          + host + ' 연결을 막거나 바꾸고 있습니다. 서버 CA 설정을 확인하세요.', flush=True)
                except Exception:
                    print('  ※ 인증서 확인 실패: pip install truststore certifi (선택 패키지) 후 다시 시도하세요.', flush=True)
            raise last  # 인증서 문제는 재시도해도 같음
        time.sleep(2 * (i + 1))
    raise last


def save_pdf(data, path):
    if not data.startswith(b'%PDF'):
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.part'); tmp.write_bytes(data); os.replace(tmp, path)
    return True


def pdf_path(out, fn):
    m = FN_RE.search(fn)
    kind, stn = (m.group(1), m.group(2)) if m else ('x', 'x')
    return out / 'pdf' / KIND_NAME.get(kind, '기타') / stn / fn

# ---------------------------------------------------------------- 1) 최신 받기

def fetch_latest(out, stns, with_cmt=True):
    got = 0
    for kind in ('1', '3'):
        for stn in stns:
            try:
                data, _ = http_get(LIST_API.format(kind=kind, stn=stn))
                j = json.loads(data.decode('utf-8'))
            except Exception as e:
                log('목록', f'{KIND_NAME[kind]} {stn}', '실패', repr(e)[:200]); continue
            fns = [j.get('filename')] + ([j.get('cmtfilename')] if with_cmt else [])
            for fn in [x for x in fns if x]:
                p = pdf_path(out, fn)
                if p.exists() and p.stat().st_size > 1000:
                    log('PDF', fn, '있음'); continue
                try:
                    data, ctype = http_get(PDF_URL.format(fn=fn), timeout=120)
                    if save_pdf(data, p):
                        got += 1; log('PDF', fn, '받음', f'{len(data):,} bytes')
                    else:
                        log('PDF', fn, '실패', f'PDF 아님({ctype})')
                except Exception as e:
                    log('PDF', fn, '실패', repr(e)[:200])
    return got

# ---------------------------------------------------------------- 2) 아카이브 과거분

def fetch_wayback(out, stns, with_cmt=True):
    seen = {}
    for pre in WAYBACK_PREFIX:
        q = ('https://web.archive.org/cdx/search/cdx?url=' + urllib.parse.quote(pre, safe='/') +
             '&matchType=prefix&output=json&fl=original,timestamp,statuscode,mimetype'
             '&filter=statuscode:200&filter=mimetype:application/pdf&collapse=urlkey&limit=20000')
        try:
            data, _ = http_get(q, timeout=120, sleep=2)
            rows = json.loads(data.decode('utf-8') or '[]')[1:]
        except Exception as e:
            log('아카이브목록', pre, '실패', repr(e)[:200]); continue
        n = 0
        for orig, ts, sc, mt in rows:
            fn = orig.split('?')[0].rsplit('/', 1)[-1]
            m = FN_RE.search(fn)
            if not m or m.group(2) not in stns or (m.group(3) and not with_cmt):
                continue
            seen.setdefault(fn, (orig, ts)); n += 1
        log('아카이브목록', pre, '확인', f'전망 PDF {n}개')
    got = 0
    for fn, (orig, ts) in sorted(seen.items()):
        p = pdf_path(out, fn)
        if p.exists() and p.stat().st_size > 1000:
            continue
        try:
            data, ctype = http_get(f'https://web.archive.org/web/{ts}id_/{orig}', timeout=180, sleep=3)
            if save_pdf(data, p):
                got += 1; log('아카이브PDF', fn, '받음', f'저장시점 {ts}')
            else:
                log('아카이브PDF', fn, '실패', f'PDF 아님({ctype})')
        except Exception as e:
            log('아카이브PDF', fn, '실패', repr(e)[:200])
    log('아카이브', '전체', '완료', f'후보 {len(seen)}개, 새로 받음 {got}개')
    return got

# ---------------------------------------------------------------- 3) PDF → 표

def norm(s):
    return re.sub(r'\s+', ' ', s.replace('　', ' ')).strip()


def region_code(name):
    n = name.replace(' ', '')
    rules = [('전국', '108'), ('영서', '101'), ('영동', '105'), ('서울', '109'), ('경기', '109'),
             ('충청북', '131'), ('충북', '131'), ('충청남', '133'), ('충남', '133'), ('대전', '133'),
             ('전라북', '146'), ('전북', '146'), ('전라남', '156'), ('전남', '156'), ('광주', '156'),
             ('경상북', '143'), ('경북', '143'), ('대구', '143'), ('경상남', '159'), ('경남', '159'), ('부산', '159'),
             ('제주', '184'), ('평안', 'NKW'), ('황해', 'NKW'), ('함경', 'NKE')]
    for k, c in rules:
        if k in n:
            return c
    return ''


def fix_probs(tokens):
    """['20','40','4','0'] 처럼 숫자가 쪼개져 나와도 합 100인 세 값으로 맞춤"""
    t = [x for x in tokens if x]
    def ok(v):
        return len(v) == 3 and sum(v) == 100 and all(0 <= x <= 100 for x in v)
    v = [int(x) for x in t]
    if ok(v):
        return v, ''
    n = len(t)
    if 3 < n <= 7:
        for cut in combinations(range(1, n), 2):
            parts = [t[:cut[0]], t[cut[0]:cut[1]], t[cut[1]:]]
            vv = [int(''.join(p)) for p in parts]
            if ok(vv) and all(x % 10 == 0 for x in vv):
                return vv, '숫자 붙여 맞춤'
    return None, f'확률 해석 실패({" ".join(t)})'


def parse_meta(text, fn):
    t = norm(text)
    m = FN_RE.search(fn)
    meta = dict(파일명=fn, 전망종류=KIND_NAME.get(m.group(1), '') if m else '', 지점=m.group(2) if m else '',
                해설서='Y' if (m and m.group(3)) else '', 파일날짜=m.group(4) if m else '')
    issue = nxt = ''
    for mm in re.finditer(r'(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일\s*(\d{1,2})\s*시\s*발표', t):
        s = f'{mm.group(1)}-{int(mm.group(2)):02d}-{int(mm.group(3)):02d} {int(mm.group(4)):02d}:00'
        if '다음' in t[max(0, mm.start() - 40):mm.start()]:
            nxt = nxt or s
        else:
            issue = issue or s
    if not issue and meta['파일날짜']:
        d = meta['파일날짜']; issue = f'{d[:4]}-{d[4:6]}-{d[6:]} 11:00'
    meta['발표일시'] = issue; meta['다음발표'] = nxt
    pm = re.search(r'(\d{4})\s*년\s*(\d{1,2})\s*월\s*(?:(\d{1,2})\s*일\s*)?~\s*(?:(\d{4})\s*년\s*)?(?:(\d{1,2})\s*월\s*)?(\d{1,2})\s*(일|월)', t)
    meta['전망기간_원문'] = pm.group(0) if pm else ''
    meta['전망시작연도'] = int(pm.group(1)) if pm else (int(issue[:4]) if issue else None)
    meta['전망시작월'] = int(pm.group(2)) if pm else (int(issue[5:7]) if issue else None)
    en = re.search(r'엘니뇨\s*/\s*라니냐\s*전망\s*:\s*(.{0,400}?)(?:※|■|$)', t)
    meta['엔소전망'] = en.group(1).strip() if en else ''
    return meta


def ymd_from_md(month, day, meta):
    y0, m0 = meta['전망시작연도'], meta['전망시작월']
    if y0 is None:
        return ''
    y = y0 + (1 if (m0 and month < m0 - 6) else 0)
    try:
        return dt.date(y, month, day).isoformat()
    except ValueError:
        return ''


def month_span(month, meta):
    y0, m0 = meta['전망시작연도'], meta['전망시작월']
    if y0 is None:
        return '', ''
    y = y0 + (1 if (m0 and month < m0) else 0)
    s = dt.date(y, month, 1)
    e = (dt.date(y + (month == 12), month % 12 + 1, 1) - dt.timedelta(days=1))
    return s.isoformat(), e.isoformat()


RANGE = r'(-?\d+(?:\.\d+)?)\s*~\s*(-?\d+(?:\.\d+)?)'
_M1 = r'(?:\d{1,2}\s*월?\s*~\s*\d{1,2}\s*월|\d{1,2}\s*월)'
MONTHS = r'(' + _M1 + r'(?:\s*,\s*' + _M1 + r')*)'


def expand_months(txt):
    """'10 월 , 12 월' → [10, 12] / '10~12 월' → [10, 11, 12] / '12~2월' → [12, 1, 2]"""
    out = []
    for part in re.split(r'\s*,\s*', txt):
        m = re.match(r'(\d{1,2})\s*월?\s*~\s*(\d{1,2})', part)
        if m:
            a, b = int(m.group(1)), int(m.group(2)); x = a
            while True:
                out.append(x)
                if x == b or len(out) > 12:
                    break
                x = x % 12 + 1
        else:
            m = re.match(r'(\d{1,2})', part)
            if m:
                out.append(int(m.group(1)))
    return out


def parse_tables(pages, meta):
    rows = []
    for pi, raw in enumerate(pages, 1):
        t = norm(raw)
        if '평년비슷' not in t or '확률 전망' not in t:
            continue
        elem = '평균기온' if '평균기온 확률 전망' in t else ('강수량' if '강수량 확률 전망' in t else '')
        if not elem:
            continue
        head_i = t.find('평년비슷')
        h0 = t.rfind('지역', 0, head_i)
        header = t[h0:head_i] if h0 >= 0 else t[:head_i]
        if meta['전망종류'] == '1개월':
            periods = []
            for mm in re.finditer(r'(\d)\s*주\s*\(\s*(\d{1,2})\.\s*(\d{1,2})\.\s*~\s*(\d{1,2})\.\s*(\d{1,2})\.?\s*\)', header):
                periods.append(dict(기간순번=int(mm.group(1)), 기간=f'{mm.group(1)}주',
                                    기간시작=ymd_from_md(int(mm.group(2)), int(mm.group(3)), meta),
                                    기간끝=ymd_from_md(int(mm.group(4)), int(mm.group(5)), meta)))
        else:
            periods = []
            for k, mm in enumerate(re.finditer(r'(\d{1,2})\s*월', header), 1):
                s, e = month_span(int(mm.group(1)), meta)
                periods.append(dict(기간순번=k, 기간=f'{int(mm.group(1))}월', 기간시작=s, 기간끝=e))
        cats = re.findall(r'(낮음|적음|비슷|높음|많음)\s*\(\s*%\s*\)', t[head_i:])[:3]
        order = ['하', '중', '상']
        if len(cats) == 3:
            pos = {'낮음': '하', '적음': '하', '비슷': '중', '높음': '상', '많음': '상'}
            order = [pos[c] for c in cats]
        last = [mm.end() for mm in re.finditer(r'\(\s*%\s*\)', t)]
        body = t[last[-1]:] if last else t[head_i:]
        body = re.sub(r'-\s*\d+\s*-\s*$', '', body).strip()
        row_re = re.compile(r'([가-힣][가-힣ㆍ·・,()\s]*?)\s*((?:' + RANGE + r'(?:\s+\d+(?![\d.]))+\s*)+)')
        for rm in row_re.finditer(body):
            name = rm.group(1).strip(); code = region_code(name)
            nums = rm.group(2)
            rngs = list(re.finditer(RANGE, nums))
            for k, r1 in enumerate(rngs):
                seg = nums[r1.end(): rngs[k + 1].start() if k + 1 < len(rngs) else len(nums)]
                probs, note = fix_probs(re.findall(r'\d+', seg))
                per = periods[k] if k < len(periods) else dict(기간순번=k + 1, 기간='', 기간시작='', 기간끝='')
                d = dict(지역_원문=name, 지역코드=code, 지역=STN_NAME.get(code, ''), 요소=elem, **per,
                         평년범위_하=float(r1.group(1)), 평년범위_상=float(r1.group(2)), 출처=f'표(p{pi})', 메모=note)
                if probs:
                    v = dict(zip(order, probs)); d.update(확률_하=v['하'], 확률_중=v['중'], 확률_상=v['상'])
                rows.append(d)
    return rows


def parse_sentences(pages, meta):
    """지역 PDF 2쪽 문장: (주평균기온) 평년(a~b℃)... ※ 확률전망(%): 낮음 x, 비슷 y, 높음 z"""
    t = norm(' '.join(pages))
    code = meta['지점']; rows = []
    prob_re = re.compile(r'확률전망\s*\(\s*%\s*\)\s*:\s*(낮음|적음)\s*(\d+)\s*,\s*비슷\s*(\d+)\s*,\s*(높음|많음)\s*(\d+)')
    if meta['전망종류'] == '1개월':
        marks = [(mm.start(), mm) for mm in re.finditer(r'(\d{1,2})\.(\d{1,2})\.\s*~\s*(\d{1,2})\.(\d{1,2})\.', t)]
        k = 0
        for em in re.finditer(r'\((주평균기온|주강수량)\)\s*평년\(\s*' + RANGE + r'\s*(?:℃|㎜|mm)?\s*\)', t):
            pm = prob_re.search(t, em.end())
            nxt = re.search(r'\((주평균기온|주강수량)\)', t[em.end():])
            if not pm or (nxt and em.end() + nxt.start() < pm.start()):
                continue
            prev = [mm for pos, mm in marks if pos < em.start()]
            if not prev:
                continue
            mm = prev[-1]
            s = ymd_from_md(int(mm.group(1)), int(mm.group(2)), meta); e = ymd_from_md(int(mm.group(3)), int(mm.group(4)), meta)
            rows.append(dict(지역_원문=STN_NAME.get(code, code), 지역코드=code, 지역=STN_NAME.get(code, ''),
                             요소='평균기온' if em.group(1) == '주평균기온' else '강수량', 기간순번=None, 기간='', 기간시작=s, 기간끝=e,
                             평년범위_하=float(em.group(2)), 평년범위_상=float(em.group(3)),
                             확률_하=int(pm.group(2)), 확률_중=int(pm.group(3)), 확률_상=int(pm.group(5)), 출처='문장', 메모=''))
        starts = sorted({r['기간시작'] for r in rows})
        for r in rows:
            r['기간순번'] = starts.index(r['기간시작']) + 1; r['기간'] = f"{r['기간순번']}주"
    else:
        rng = {}
        # 월별 전망: '10월 ... (월평균기온) 평년(a~b℃) ... (월강수량) 평년(a~b㎜)'
        sec = t[t.find('월별 전망'):] if '월별 전망' in t else t
        blocks = list(re.finditer(r'(?:^|\s)(\d{1,2})\s*월\s', sec))
        for i, b in enumerate(blocks):
            seg = sec[b.end(): blocks[i + 1].start() if i + 1 < len(blocks) else len(sec)]
            for el, key in (('평균기온', '월평균기온'), ('강수량', '월강수량')):
                mm = re.search(r'\(' + key + r'\)\s*평년\(\s*' + RANGE, seg)
                if mm:
                    rng.setdefault((int(b.group(1)), el), (float(mm.group(1)), float(mm.group(2))))
        summ = t[t.find('전망 요약'):t.find('월별 전망')] if '전망 요약' in t else ''
        probs = {}
        for el, a, b_ in (('평균기온', '기온 전망', '강수량 전망'), ('강수량', '강수량 전망', '엘니뇨')):
            i0 = summ.find(a); i1 = summ.find(b_, i0 + 1) if i0 >= 0 else -1
            part = summ[i0:i1 if i1 > 0 else len(summ)] if i0 >= 0 else ''
            for mm in re.finditer(MONTHS + r'\s*(?:은|는).{0,80}?' + prob_re.pattern, part):
                for mo in expand_months(mm.group(1)):
                    probs[(mo, el)] = (int(mm.group(3)), int(mm.group(4)), int(mm.group(6)))
        months = []
        for (mo, el) in list(rng.keys()) + list(probs.keys()):
            if mo not in months:
                months.append(mo)
        for k, mo in enumerate(months, 1):
            s, e = month_span(mo, meta)
            for el in ('평균기온', '강수량'):
                if (mo, el) not in rng and (mo, el) not in probs:
                    continue
                lo, hi = rng.get((mo, el), (None, None)); p = probs.get((mo, el), (None, None, None))
                rows.append(dict(지역_원문=STN_NAME.get(code, code), 지역코드=code, 지역=STN_NAME.get(code, ''), 요소=el,
                                 기간순번=k, 기간=f'{mo}월', 기간시작=s, 기간끝=e, 평년범위_하=lo, 평년범위_상=hi,
                                 확률_하=p[0], 확률_중=p[1], 확률_상=p[2], 출처='문장', 메모='' if p[0] is not None else '확률 없음'))
    return rows


def extract_pages(path):
    from pypdf import PdfReader
    r = PdfReader(str(path))
    return [(pg.extract_text() or '') for pg in r.pages]


def judge(r):
    v = [r.get('확률_하'), r.get('확률_중'), r.get('확률_상')]
    if None in v or '' in v:
        return ''
    lab = (['낮음', '비슷', '높음'] if r['요소'] == '평균기온' else ['적음', '비슷', '많음'])
    mx = max(v)
    return '/'.join(l for l, x in zip(lab, v) if x == mx)


OUT_FIELDS = ['발표일시', '다음발표', '전망종류', '지역코드', '지역', '지역_원문', '요소', '기간순번', '기간', '기간시작', '기간끝',
              '평년범위_하', '평년범위_상', '확률_하', '확률_중', '확률_상', '최대확률범주', '출처', '파일명', '메모']


def build_csv(out):
    pdfs = sorted((out / 'pdf').rglob('*.pdf'))
    allrows, plist = [], []
    (out / 'text').mkdir(parents=True, exist_ok=True)
    for p in pdfs:
        fn = p.name
        try:
            pages = extract_pages(p)
        except Exception as e:
            plist.append(dict(파일명=fn, 상태=f'읽기실패 {e!r}'[:200])); continue
        (out / 'text' / (p.stem + '.txt')).write_text('\n\n=====PAGE=====\n\n'.join(pages), encoding='utf-8')
        meta = parse_meta(' '.join(pages), fn)
        if meta['해설서'] == 'Y':
            plist.append(dict(**{k: meta[k] for k in ('파일명', '전망종류', '지점', '발표일시', '다음발표')}, 쪽수=len(pages),
                              표행수=0, 문장행수=0, 상태='해설서(표 추출 안 함)', 엔소전망=meta['엔소전망']))
            continue
        trows = parse_tables(pages, meta) if meta['지점'] == '108' else []
        srows = parse_sentences(pages, meta)
        for r in trows + srows:
            r.update(발표일시=meta['발표일시'], 다음발표=meta['다음발표'], 전망종류=meta['전망종류'], 파일명=fn)
            r['최대확률범주'] = judge(r)
            allrows.append(r)
        bad = sum(1 for r in trows + srows if r.get('확률_하') is None or not r.get('지역코드') or not r.get('기간시작'))
        plist.append(dict(파일명=fn, 전망종류=meta['전망종류'], 지점=meta['지점'], 발표일시=meta['발표일시'], 다음발표=meta['다음발표'],
                          전망기간=meta['전망기간_원문'], 쪽수=len(pages), 표행수=len(trows), 문장행수=len(srows),
                          상태='확인필요' if (bad or not (trows or srows)) else '정상', 엔소전망=meta['엔소전망']))
        log('추출', fn, '완료', f'표 {len(trows)} / 문장 {len(srows)} / 확인필요 {bad}')
    csvd = out / 'csv'; csvd.mkdir(parents=True, exist_ok=True)
    def w(name, rows, fields):
        with open(csvd / name, 'w', newline='', encoding='utf-8-sig') as fh:
            wr = csv.DictWriter(fh, fieldnames=fields, extrasaction='ignore'); wr.writeheader(); wr.writerows(rows)
    allrows.sort(key=lambda r: (r['발표일시'], r['전망종류'], r['지역코드'], r['요소'], r['기간순번'] or 0, r['출처']))
    w('00_추출_전체.csv', allrows, OUT_FIELDS)
    # 정리본: 같은 발표·지역·요소·기간은 표(전국 PDF) 우선, 없으면 지역 PDF 문장
    best = {}
    for r in allrows:
        k = (r['발표일시'][:10], r['전망종류'], r['지역코드'], r['요소'], r['기간시작'])
        pri = 0 if r['출처'].startswith('표') else 1
        if k not in best or pri < best[k][0]:
            best[k] = (pri, r)
    clean = [v[1] for v in best.values()]
    # 표와 문장이 다르면 표시
    sent = {(s['발표일시'][:10], s['전망종류'], s['지역코드'], s['요소'], s['기간시작']): s for s in allrows if s['출처'] == '문장'}
    for r in clean:
        if r['출처'].startswith('표'):
            s = sent.get((r['발표일시'][:10], r['전망종류'], r['지역코드'], r['요소'], r['기간시작']))
            if s and s.get('확률_하') is not None and \
                    (s['확률_하'], s['확률_중'], s['확률_상']) != (r.get('확률_하'), r.get('확률_중'), r.get('확률_상')):
                r['메모'] = (r.get('메모', '') + ' 지역PDF 문장과 확률 다름').strip()
    clean.sort(key=lambda r: (r['발표일시'], r['전망종류'], r['지역코드'], r['요소'], r['기간순번'] or 0))
    w('01_장기전망_지역별_확률.csv', clean, OUT_FIELDS)
    w('02_발표목록.csv', plist, ['파일명', '전망종류', '지점', '발표일시', '다음발표', '전망기간', '쪽수', '표행수', '문장행수', '상태', '엔소전망'])
    log('CSV', str(csvd), '완료', f'PDF {len(pdfs)}개 / 전체 {len(allrows)}행 / 정리 {len(clean)}행')


def write_log(out):
    p = out / '수집로그.csv'; new = not p.exists()
    with open(p, 'a', newline='', encoding='utf-8-sig') as fh:
        wr = csv.DictWriter(fh, fieldnames=['시각', '작업', '대상', '결과', '메모'])
        if new:
            wr.writeheader()
        wr.writerows(LOG)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--part', default='latest', choices=['latest', 'wayback', 'parse', 'all'])
    ap.add_argument('--output', default=str(wxcommon.data_dir() / 'raw' / 'longrange'))
    ap.add_argument('--test', action='store_true', help='전국(108)만, test_data에')
    ap.add_argument('--no-cmt', action='store_true', help='3개월 해설서(cmt, 약 4MB) 받지 않기')
    a = ap.parse_args()
    out = Path(a.output if not a.test else 'test_data'); out.mkdir(parents=True, exist_ok=True)
    stns = ['108'] if a.test else STNS
    wxcommon.start()
    try:
        import pypdf  # noqa
    except ImportError:
        print('pypdf 가 없습니다. pip install -r requirements.txt 를 먼저 실행하세요.', flush=True)
        wxcommon.error('pypdf 없음'); sys.exit(wxcommon.EXIT_FAIL)
    try:
        if a.part in ('latest', 'all'):
            wxcommon.STATS['added'] += fetch_latest(out, stns, not a.no_cmt)   # 추가 = 새로 받은 PDF 수
        if a.part in ('wayback', 'all'):
            wxcommon.STATS['added'] += fetch_wayback(out, stns, not a.no_cmt)
        build_csv(out)
    finally:
        write_log(out)
    bad = [f"{r['작업']} {r['대상']}: {r['메모'][:120]}" for r in LOG if r['결과'] == '실패']
    for b in bad:
        wxcommon.error(b)
    if bad:
        sys.exit(wxcommon.EXIT_FAIL)


if __name__ == '__main__':
    main()

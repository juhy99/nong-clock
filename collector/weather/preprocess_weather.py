"""기상 통합: ASOS(종관) + AWS(방재) + 농진청 농업기상 — 원본 → 전처리 → 연결 (2026-10-16)

원래 파일: 기상_통합_전처리.py (리눅스 서버용으로 --base 기본값과 --link 옵션만 바꿈/추가)
서버 기본 폴더: --base data/integrated (01_원본, 02_전처리, 전처리_점검.json), --link data/link (= 03_연결)
보통은 run.py preprocess 가 01_원본에 수집 결과를 복사한 뒤 이 스크립트를 실행함.

폴더 구조 (기준 폴더 = --base)
  01_원본/ASOS/     ASOS_일자료_2015_2026_API.csv, 지점정보_원본.txt, asos_일자료_통합_1991_2025.zip
  01_원본/AWS/      원본/{요소}_{연도}.txt.gz (기상청 API허브 지상·AWS 일통계), 연월별_전체지점목록.csv, (선택) AWS_지점정보_원본.txt
  01_원본/농업기상/  농업기상_일자료_통합.csv, 관측지점_목록.csv (농진청 농업기상 기본관측 V3)
  02_전처리/ASOS|AWS|농업기상/YYYY.csv  출처별 정제(같은 열 이름, 범위점검, 결측코드 정리)
  03_연결/(--link)  일자료_연도별/YYYY.csv (세 관측망 한 표), 관측지점_마스터.csv,
                    시도별_일기상.csv, 지점별_월기상.csv, 시도별_월기상.csv, 시군구별_월기상.csv, 교차검증.csv
  전처리_점검.json
실행: python preprocess_weather.py --base data/integrated --link data/link --step all   pandas 필요
"""
import argparse, gzip, io, json, os, pathlib, re, zipfile
import numpy as np, pandas as pd

VARS = ['평균기온', '최고기온', '최저기온', '강수량', '최다1시간강수', '평균습도', '최저습도', '평균풍속',
        '최대풍속', '최대순간풍속', '일조시간', '일사량', '결로시간', '초상온도', '지중온도', '토양수분']
AWS_OBS = {'ta_max': '최고기온', 'ta_min': '최저기온', 'rn_day': '강수량', 'ws_max': '최대풍속', 'ws_ins_max': '최대순간풍속'}
AWSV = list(AWS_OBS.values())
BOUNDS = {'평균기온': (-40, 45), '최고기온': (-40, 45), '최저기온': (-45, 40), '강수량': (0, 900),
          '최다1시간강수': (0, 200), '평균습도': (0, 100), '최저습도': (0, 100), '평균풍속': (0, 60),
          '최대풍속': (0, 80), '최대순간풍속': (0, 100), '일조시간': (0, 15), '일사량': (0, 40),
          '결로시간': (0, 24), '초상온도': (-45, 70), '지중온도': (-30, 50), '토양수분': (0, 100)}
AGRI = {'temp': '평균기온', 'hghst_Artmp': '최고기온', 'lowst_Artmp': '최저기온', 'hum': '평균습도',
        'wind': '평균풍속', 'max_Wind': '최대풍속', 'rn': '강수량', 'sun_Time': '일조시간', 'srqty': '일사량',
        'condens_Time': '결로시간', 'gr_Temp': '초상온도', 'soil_Temp': '지중온도', 'soil_Wt': '토양수분'}
SIDO = {'서울': '서울', '부산': '부산', '대구': '대구', '인천': '인천', '광주': '광주', '대전': '대전',
        '울산': '울산', '세종': '세종', '경기': '경기', '강원': '강원', '충청북': '충북', '충북': '충북',
        '충청남': '충남', '충남': '충남', '전라북': '전북', '전북': '전북', '전라남': '전남', '전남': '전남',
        '경상북': '경북', '경북': '경북', '경상남': '경남', '경남': '경남', '제주': '제주'}
LAW2SIDO = {'11': '서울', '26': '부산', '27': '대구', '28': '인천', '29': '광주', '30': '대전', '31': '울산',
            '36': '세종', '41': '경기', '42': '강원', '51': '강원', '43': '충북', '44': '충남', '45': '전북',
            '52': '전북', '46': '전남', '47': '경북', '48': '경남', '50': '제주'}
METRO = {'서울시': '서울', '부산시': '부산', '대구시': '대구', '인천시': '인천', '대전시': '대전', '울산시': '울산', '세종시': '세종'}
AGRI_EXTRA = {'청주시': '충북', '증평군': '충북', '수원시': '경기', '김포시': '경기', '고양시': '경기', '의정부시': '경기',
              '남양주시': '경기', '당진시': '충남', '성주군': '경북', '강릉시': '강원', '태백시': '강원', '서귀포시': '제주'}
import time
_T0 = time.time(); LIMIT = [0]
LINK = [None]   # 03_연결 폴더 (main에서 정함)
LINKVER = 2   # 연결 규칙 버전: 바꾸면 연결 단계 전 연도 다시 계산


def time_up():
    return LIMIT[0] > 0 and time.time() - _T0 > LIMIT[0]


COLS = ['날짜', '관측망', '지점', '지점명', '시도', '시군구'] + VARS + ['평균기온_근사', '강수_처리', '출처', '보완항목', '품질플래그']


# ---------- 공통 ----------
def clean_addr(a):
    return re.sub(r'^\(.*?\)', '', str(a or '')).strip()


def sido_of(addr, law=None):
    a = clean_addr(addr)
    if a.startswith('전남광주통합'):   # 2026 통합 주소: 자치구 → 광주, 시·군 → 전남 (과거 통계와 맞춤)
        t = a.split()
        return '광주' if len(t) > 1 and t[1].endswith('구') else '전남'
    for k, v in SIDO.items():
        if a.startswith(k):
            return v
    return LAW2SIDO.get(str(law or '')[:2]) if law and str(law) != 'nan' else None


def sigungu_of(addr):
    t = clean_addr(addr).split()
    if len(t) < 2:
        return None
    s = t[1]
    if len(t) > 2 and s.endswith('시') and t[2].endswith('구'):
        s = s + ' ' + t[2]
    m = re.match(r'^(\S+시)(\S+구)$', s)          # '수원시권선구' → '수원시 권선구'
    return f'{m.group(1)} {m.group(2)}' if m else s


def qc(df, cnt):
    flags = pd.Series('', index=df.index, dtype=object)
    for v, (lo, hi) in BOUNDS.items():
        if v in df:
            bad = df[v].notna() & ((df[v] < lo) | (df[v] > hi))
            if bad.any():
                cnt[v] = cnt.get(v, 0) + int(bad.sum())
                df.loc[bad, v] = np.nan
                flags[bad] += v + '범위밖;'
    inv = df['최고기온'] < df['최저기온']
    if inv.any():
        df.loc[inv, ['최고기온', '최저기온']] = np.nan
        flags[inv] += '최고<최저;'
        cnt['최고<최저'] = cnt.get('최고<최저', 0) + int(inv.sum())
    df['품질플래그'] = flags.str.rstrip(';')
    return df


def full(df):
    for v in VARS:
        if v not in df:
            df[v] = np.nan
    return df


def stn_inf(path, net):
    if not path.exists():
        return pd.DataFrame()
    rows = []
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
        if line.startswith('#') or not line.strip():
            continue
        t = line.split()
        m = re.search(r'\s(\d{10})\s+(\S+)\s+(.*)$', line)
        try:
            rows.append({'지점': int(t[0]), '경도': float(t[1]), '위도': float(t[2]),
                         '고도': float(t[4]) if net == 'ASOS' else np.nan,
                         '지점명': t[10] if net == 'ASOS' else None,
                         '법정동코드': m.group(1) if m else None, '주소': m.group(3).strip() if m else None})
        except (ValueError, IndexError):
            continue
    return pd.DataFrame(rows).drop_duplicates('지점', keep='last') if rows else pd.DataFrame()


# ---------- 2단계: 출처별 전처리 ----------
def prep_asos(base, rep):
    src = base / '01_원본/ASOS'
    out = base / '02_전처리/ASOS'; out.mkdir(parents=True, exist_ok=True)
    r = rep.setdefault('ASOS', {}); cnt = {}
    parts = []
    z = src / 'asos_일자료_통합_1991_2025.zip'
    if z.exists():
        with zipfile.ZipFile(z) as zf:
            name = [n for n in zf.namelist() if n.lower().endswith('.csv')][0]
            o = pd.read_csv(io.BytesIO(zf.read(name)), low_memory=False)
        r['1991_2025파일'] = {'행': len(o), '기간': [str(o['날짜'].min()), str(o['날짜'].max())],
                            '주의': '행수 1,048,575 = 엑셀 최대 행수 → 뒤쪽 지점 잘림(289는 2020-09-13까지, 294·295 없음). 2014년 이전만 사용'}
        o = o[(o['날짜'] < '2015-01-01') & ~o['지점'].isin([0, 8, 9])].copy()
        o['강수_처리'] = np.where(o['강수량'].notna(), '원값', '결측')
        o['출처'] = 'ASOS(1991~2014 파일)'
        parts.append(o)
    n = pd.read_csv(src / 'ASOS_일자료_2015_2026_API.csv')
    n = n[~n['지점'].isin([0, 8, 9])].copy()
    neg = n['강수원본값'] == -9
    n['강수_처리'] = np.select([neg, n['강수량'].notna()], ['-9→0(무강수 추정)', '원값'], '결측')
    n.loc[neg, '강수량'] = 0.0
    r['2015~_강수-9→0'] = int(neg.sum())
    n['출처'] = 'ASOS(API 2015~)'
    parts.append(n)
    d = full(pd.concat(parts, ignore_index=True))
    d['날짜'] = d['날짜'].astype(str)
    d = d.drop_duplicates(['날짜', '지점'], keep='last')
    d = qc(d, cnt)
    r['QC_결측처리'] = cnt
    r['행'] = len(d); r['지점수'] = int(d['지점'].nunique()); r['기간'] = [d['날짜'].min(), d['날짜'].max()]
    keep = ['날짜', '지점'] + VARS + ['강수_처리', '출처', '품질플래그']
    for y, g in d.groupby(d['날짜'].str[:4]):
        g[keep].to_csv(out / f'{y}.csv', index=False, encoding='utf-8-sig')
    return sorted(d['지점'].unique().tolist())


def parse_aws(raw):
    text = raw.decode('cp949', errors='replace')
    rows = []
    for line in text.splitlines():
        if not line or line.startswith('#'):
            continue
        p = line.split(',')
        if len(p) >= 7:
            rows.append(p[:6] + [p[6].rstrip('=').strip()])
    return rows


def prep_aws(base, rep):
    src = base / '01_원본/AWS/원본'
    out = base / '02_전처리/AWS'; out.mkdir(parents=True, exist_ok=True)
    r = rep.setdefault('AWS', {}); cnt = r.setdefault('QC_결측처리', {}); total = 0
    years = sorted({int(f.name.split('_')[-1][:4]) for f in src.glob('ta_max_*.txt.gz')})
    (out / '_좌표').mkdir(exist_ok=True)
    for y in years:
        if (out / f'{y}.csv').exists() and (out / '_좌표' / f'{y}.csv').exists():
            continue                                    # 이미 처리한 연도 (이어하기)
        meta = {}
        wide = None
        for obs, name in AWS_OBS.items():
            f = src / f'{obs}_{y}.txt.gz'
            if not f.exists():
                continue
            df = pd.DataFrame(parse_aws(gzip.decompress(f.read_bytes())),
                              columns=['날짜', '지점', '경도', '위도', '고도', name, '지점명'])
            if obs == 'ta_max':
                rng = df.groupby('지점')['날짜'].agg(['min', 'max'])
                for row in df.drop_duplicates('지점', keep='last').itertuples():
                    k = int(row.지점)
                    first = meta.get(k, {}).get('첫날', rng.at[row.지점, 'min'])
                    meta[k] = {'경도': row.경도, '위도': row.위도, '고도': row.고도, '지점명_AWS': row.지점명,
                               '첫날': min(first, rng.at[row.지점, 'min']), '끝날': rng.at[row.지점, 'max']}
            df = df[['날짜', '지점', name]]
            df[name] = pd.to_numeric(df[name], errors='coerce')
            df.loc[df[name] <= -50, name] = np.nan            # 결측코드(-99 등)
            df = df.drop_duplicates(['날짜', '지점'], keep='last')
            wide = df if wide is None else wide.merge(df, on=['날짜', '지점'], how='outer')
        if wide is None:
            continue
        wide['날짜'] = pd.to_datetime(wide['날짜'], format='%Y%m%d').dt.strftime('%Y-%m-%d')
        wide['지점'] = wide['지점'].astype(int)
        wide = qc(wide, cnt)
        wide['강수_처리'] = np.where(wide['강수량'].notna(), '원값', '결측')
        wide['출처'] = 'AWS일통계'
        wide.sort_values(['날짜', '지점'])[['날짜', '지점'] + AWSV + ['강수_처리', '출처', '품질플래그']].to_csv(
            out / f'{y}.csv', index=False, encoding='utf-8-sig')
        pd.DataFrame([{'지점': k, **v} for k, v in meta.items()]).to_csv(out / '_좌표' / f'{y}.csv', index=False, encoding='utf-8-sig')
        total += len(wide)
        print(f'  AWS {y}: {len(wide):,}행', flush=True)
        if time_up():
            print('  (시간 제한: 다음 실행에서 이어서)', flush=True)
            return False
    parts = [pd.read_csv(f, dtype=str) for f in sorted((out / '_좌표').glob('*.csv'))]
    m = pd.concat(parts, ignore_index=True)
    first = m.groupby('지점')['첫날'].min()
    m = m.drop_duplicates('지점', keep='last').set_index('지점')
    m['첫날'] = first
    m = m.reset_index()
    for c in ('경도', '위도', '고도'):
        m[c] = pd.to_numeric(m[c], errors='coerce')
    for c in ('첫날', '끝날'):
        m[c] = pd.to_datetime(m[c], format='%Y%m%d').dt.strftime('%Y-%m-%d')
    m['지점'] = m['지점'].astype(int)
    m.to_csv(out / '_지점좌표.csv', index=False, encoding='utf-8-sig')
    r.update({'행(이번 실행)': total, '지점수': len(m), '연도': [years[0], years[-1]] if years else None,
              '설명': '기상청 API허브 지상·AWS 일통계(sfc_aws_day). ASOS 지점 포함. 0 포함 응답 → 행 없음은 미관측'})
    return True


def agri_sido(name):
    t = str(name).split()
    if not t:
        return None, None
    tok = t[0] if t[0].endswith(('시', '군')) else t[0] + '시'
    sec = t[1] if len(t) > 1 else ''
    if tok == '광주시':                                 # 광주광역시(구) vs 경기 광주시(동·읍·면)
        return ('광주', sec) if sec.endswith('구') else ('경기', '광주시')
    if tok in METRO:
        return METRO[tok], (sec if sec.endswith('구') else None)
    if tok == '고성군':
        return ('강원' if sec[:2] in ('간성', '거진', '토성', '죽왕', '현내') else '경남'), '고성군'
    if tok in AGRI_EXTRA:
        sg = f'{tok} {sec}' if sec.endswith('구') and tok.endswith('시') else tok
        return AGRI_EXTRA[tok], sg
    return None, tok


def prep_agri(base, rep, sgg2sido):
    src = base / '01_원본/농업기상'
    out = base / '02_전처리/농업기상'; out.mkdir(parents=True, exist_ok=True)
    r = rep.setdefault('농업기상', {}); cnt = {}
    d = pd.read_csv(src / '농업기상_일자료_통합.csv', dtype={'stn_Cd': str}, low_memory=False)
    r['원본행'] = len(d)
    test = d['stn_Name'].astype(str).str.contains('테스트')
    r['테스트지점_제외행'] = int(test.sum())
    d = d[~test].rename(columns={**AGRI, 'stn_Cd': '지점', 'stn_Name': '지점명', 'date': '날짜'})
    dup = d.duplicated(['날짜', '지점'], keep='last')
    r['중복(지점·날짜)_제외'] = int(dup.sum())
    d = d[~dup].copy()
    for v in AGRI.values():
        d[v] = pd.to_numeric(d[v], errors='coerce')
    for v in ('일조시간', '결로시간'):                     # 분 단위 → 시간
        d[v] = (d[v] / 60).round(2)
    d.loc[d['평균기온'].abs() >= 49, '평균기온'] = np.nan      # ±50 근처 = 센서 한계값(결측성)
    d = qc(full(d), cnt)
    d['강수_처리'] = np.where(d['강수량'].notna(), '원값', '결측')
    d['출처'] = '농진청 농업기상(V3)'
    r.update({'행': len(d), '지점수': int(d['지점'].nunique()), '기간': [d['날짜'].min(), d['날짜'].max()],
              'QC_결측처리': cnt, '단위변환': '일조시간·결로시간 분→시간', '풍향(widdir)': '제외(일 평균 풍향은 의미 약함)'})
    for y, g in d.groupby(d['날짜'].str[:4]):
        g[['날짜', '지점'] + VARS + ['강수_처리', '출처', '품질플래그']].to_csv(out / f'{y}.csv', index=False, encoding='utf-8-sig')
    st = d.groupby('지점').agg(지점명=('지점명', 'last'), 첫날=('날짜', 'min'), 끝날=('날짜', 'max')).reset_index()
    sd = [agri_sido(n) for n in st['지점명']]
    st['시도'] = [a for a, _ in sd]
    st['시군구'] = [b for _, b in sd]
    miss = st['시도'].isna()
    st.loc[miss, '시도'] = st.loc[miss, '시군구'].map(sgg2sido)
    st['시도근거'] = np.where(miss, '지점명→시군구 대응', '지점명 규칙')
    st.loc[st['시도'].isna(), '시도근거'] = '확인 필요'
    st['관측망'] = '농업기상'
    return st


def build_master(base, asos_ids, rep):
    asos = stn_inf(base / '01_원본/ASOS/지점정보_원본.txt', 'ASOS')
    awsi = stn_inf(base / '01_원본/AWS/AWS_지점정보_원본.txt', 'AWS')
    lp = base / '01_원본/AWS/연월별_전체지점목록.csv'
    awsl = pd.DataFrame()
    if lp.exists():
        s = pd.read_csv(lp, dtype=str).sort_values('조회연월').drop_duplicates('지점번호', keep='last')
        awsl = pd.DataFrame({'지점': s['지점번호'].astype(int), '주소': s['addr']})
    co = pd.read_csv(base / '02_전처리/AWS/_지점좌표.csv')
    asos_all = set(asos['지점']) | set(asos_ids)
    m = pd.DataFrame({'지점': sorted(set(co['지점']) | asos_all)})
    m['관측망'] = np.where(m['지점'].isin(asos_all), 'ASOS', 'AWS')
    m = m.merge(co, on='지점', how='left')
    a = asos.set_index('지점')
    m['지점명'] = m['지점'].map(a['지점명']).combine_first(m['지점명_AWS'])
    for c in ('경도', '위도', '고도'):
        m[c] = m['지점'].map(a[c]).combine_first(m[c])
    m['법정동코드'] = m['지점'].map(a['법정동코드'])
    m['주소'] = m['지점'].map(a['주소'])
    m['주소출처'] = np.where(m['주소'].notna(), 'ASOS지점정보', None)
    for src, name in ((awsi, 'AWS지점정보(stn_inf)'), (awsl, 'AWS월보지점목록')):
        if len(src):
            s = src.drop_duplicates('지점').set_index('지점')
            need = m['주소'].isna() & m['지점'].isin(s.index)
            m.loc[need, '주소'] = m.loc[need, '지점'].map(s['주소'])
            if '법정동코드' in s:
                m.loc[need, '법정동코드'] = m.loc[need, '지점'].map(s['법정동코드'])
            m.loc[need & m['주소'].notna(), '주소출처'] = name
    m['시도'] = [sido_of(x, l) for x, l in zip(m['주소'], m['법정동코드'])]
    m['시군구'] = m['주소'].map(sigungu_of)
    m['시도근거'] = np.where(m['시도'].notna(), '주소', None)
    known = m[m['시도'].notna() & m['위도'].notna()]
    unk = m['시도'].isna() & m['위도'].notna()
    if unk.any() and len(known):                    # 주소 없는 지점: 가장 가까운 주소 있는 지점으로 추정
        la1 = np.radians(m.loc[unk, '위도'].values)[:, None]; lo1 = np.radians(m.loc[unk, '경도'].values)[:, None]
        la2 = np.radians(known['위도'].values)[None, :]; lo2 = np.radians(known['경도'].values)[None, :]
        h = np.sin((la2 - la1) / 2) ** 2 + np.cos(la1) * np.cos(la2) * np.sin((lo2 - lo1) / 2) ** 2
        dist = 6371 * 2 * np.arcsin(np.sqrt(h))
        j, dmin = dist.argmin(1), dist.min(1)
        m.loc[unk, '시도'] = known['시도'].values[j]
        m.loc[unk, '시군구'] = known['시군구'].values[j]
        m.loc[unk, '시도근거'] = [f'최근접추정({d:.1f}km,지점{int(k)})' for d, k in zip(dmin, known['지점'].values[j])]
        m.loc[unk, '최근접거리km'] = dmin.round(1)
    m = m.drop(columns=['지점명_AWS'])
    m['지점'] = m['지점'].astype(str)
    return m


def step_prep(base, rep, which):
    if which in ('asos', 'prep'):
        print('2단계 전처리: ASOS', flush=True)
        ids = prep_asos(base, rep)
        pd.Series(ids, name='지점').to_csv(base / '02_전처리/ASOS/_지점목록.csv', index=False)
    if which in ('aws', 'prep'):
        print('2단계 전처리: AWS', flush=True)
        if not prep_aws(base, rep):
            return False
    if which in ('agri', 'prep'):
        print('2단계 전처리: 지점마스터·농업기상', flush=True)
        asos_ids = pd.read_csv(base / '02_전처리/ASOS/_지점목록.csv')['지점'].tolist()
        m = build_master(base, asos_ids, rep)
        pairs = m.dropna(subset=['시도', '시군구'])
        sgg = pairs.assign(t=pairs['시군구'].str.split().str[0]).groupby('t')['시도'].agg(
            lambda s: s.iloc[0] if s.nunique() == 1 else None)
        ag = prep_agri(base, rep, sgg.dropna().to_dict())
        m = pd.concat([m, ag], ignore_index=True)
        LINK[0].mkdir(parents=True, exist_ok=True)
        m.to_csv(LINK[0] / '관측지점_마스터.csv', index=False, encoding='utf-8-sig')
        rep['지점마스터'] = {'관측망별_지점수': m['관측망'].value_counts().to_dict(),
                         '시도근거': m['시도근거'].fillna('없음').str.replace(r'\(.*', '', regex=True).value_counts().to_dict(),
                         '시도없음': m.loc[m['시도'].isna(), ['관측망', '지점', '지점명']].astype(str).values.tolist()}
    return True


# ---------- 3단계: 연결 ----------
def read_y(p, key_int=True):
    if not p.exists():
        return None
    d = pd.read_csv(p, dtype={'지점': (int if key_int else str)}, low_memory=False)
    return d


def step_link(base, rep):
    pre, out = base / '02_전처리', LINK[0]
    (out / '일자료_연도별').mkdir(parents=True, exist_ok=True)
    M = pd.read_csv(out / '관측지점_마스터.csv', dtype={'지점': str})
    asos_set = set(M.loc[M['관측망'] == 'ASOS', '지점'])
    years = sorted({p.stem for k in ('ASOS', 'AWS', '농업기상') for p in (pre / k).glob('[12]*.csv')})
    agg = out / '_집계'; agg.mkdir(exist_ok=True)
    for y in years:
        sp = agg / f'{y}_stat.json'
        if sp.exists() and json.loads(sp.read_text(encoding='utf-8')).get('ver') == LINKVER:
            continue                                    # 이미 연결한 연도 (이어하기)
        if time_up():
            print('  (시간 제한: 다음 실행에서 이어서)', flush=True)
            return False
        acc = {v: [0, 0, 0, 0.0, 0.0] for v in ['최고기온', '최저기온', '강수량', '최대풍속']}   # n, 일치, 0.5이내, 절대차합, 최대
        fills = {v: 0 for v in AWSV}; added = 0; counts = {}; spat = {}
        S = read_y(pre / 'ASOS' / f'{y}.csv'); A = read_y(pre / 'AWS' / f'{y}.csv'); N = read_y(pre / '농업기상' / f'{y}.csv', False)
        parts = []
        if A is not None:
            A['지점'] = A['지점'].astype(str)
            Aa = A[A['지점'].isin(asos_set)].drop(columns=['품질플래그', '강수_처리', '출처'])
            W = A[~A['지점'].isin(asos_set)].copy()
        else:
            Aa = pd.DataFrame({'날짜': pd.Series(dtype=str), '지점': pd.Series(dtype=str), **{v: pd.Series(dtype=float) for v in AWSV}})
            W = None
        if S is not None:
            S['지점'] = S['지점'].astype(str)
            S = S.merge(Aa, on=['날짜', '지점'], how='left', suffixes=('', '_A'), indicator='_m')
            for v in acc:
                x = S[[v, v + '_A']].dropna()
                if len(x):
                    dd = (x[v] - x[v + '_A']).abs()
                    a_ = acc[v]; a_[0] += len(dd); a_[1] += int((dd < 0.05).sum()); a_[2] += int((dd <= 0.5).sum())
                    a_[3] += float(dd.sum()); a_[4] = max(a_[4], float(dd.max()))
            S['보완항목'] = pd.Series('', index=S.index, dtype=object)
            for v in AWSV:                              # ASOS 빈 항목 ← 같은 지점 AWS일통계
                f = S[v].isna() & S[v + '_A'].notna()
                S.loc[f, v] = S.loc[f, v + '_A']; S.loc[f, '보완항목'] += v + ';'; fills[v] += int(f.sum())
            S.loc[S['강수_처리'].eq('결측') & S['강수량'].notna(), '강수_처리'] = 'AWS일통계 보완'
            got = S.loc[S['_m'] == 'both', ['날짜', '지점']].assign(_x=1)
            S = S.drop(columns=[v + '_A' for v in AWSV] + ['_m'])
            parts.append(S)
        else:
            got = pd.DataFrame(columns=['날짜', '지점', '_x'])
        if len(Aa):                                     # ASOS 지점인데 ASOS 자료 없는 날
            ad = Aa.merge(got, on=['날짜', '지점'], how='left')
            ad = ad[ad['_x'].isna()].drop(columns='_x')
            ad['출처'] = 'AWS일통계(ASOS지점·ASOS자료 없는 날)'
            ad['강수_처리'] = np.where(ad['강수량'].notna(), '원값', '결측')
            added += len(ad); parts.append(ad)
        if W is not None:
            parts.append(W)
        if N is not None:
            parts.append(N)
        D = full(pd.concat(parts, ignore_index=True))
        for v in VARS:
            D[v] = pd.to_numeric(D[v], errors='coerce')
        D = D.merge(M[['지점', '관측망', '지점명', '시도', '시군구']], on='지점', how='left')
        D['품질플래그'] = D['품질플래그'].fillna('').astype(str)
        for v in ('평균기온', '최고기온', '최저기온'):   # 공간 점검: 같은 날·같은 시도 중앙값과 15℃ 넘게 차이 → 결측
            med = D.groupby(['날짜', '시도'])[v].transform('median')
            bad = (D[v] - med).abs() > 15
            if bad.any():
                D.loc[bad, v] = np.nan
                D.loc[bad, '품질플래그'] = D.loc[bad, '품질플래그'].str.rstrip(';') + ';' + v + '공간이상'
                spat[v] = spat.get(v, 0) + int(bad.sum())
        D['평균기온_근사'] = ((D['최고기온'] + D['최저기온']) / 2).round(2)
        for c in ('보완항목', '품질플래그'):
            D[c] = D[c].fillna('').astype(str).str.strip(';') if c in D else ''
        D = D.sort_values(['날짜', '관측망', '지점'])[COLS]
        D.to_csv(out / '일자료_연도별' / f'{y}.csv', index=False, encoding='utf-8-sig')
        for k, v in D['관측망'].value_counts().items():
            counts[k] = counts.get(k, 0) + int(v)
        # 집계용
        d = D[D['시도'].notna()].copy()
        d['고온일'] = (d['최고기온'] >= 33).astype(float).where(d['최고기온'].notna())
        d['영하일'] = (d['최저기온'] < 0).astype(float).where(d['최저기온'].notna())
        d['강수일'] = (d['강수량'] >= 1).astype(float).where(d['강수량'].notna())
        d['강풍일'] = (d['최대순간풍속'] >= 14).astype(float).where(d['최대순간풍속'].notna())
        for net in ('ASOS', 'AWS', '농업기상'):
            d['n_' + net] = ((d['관측망'] == net) & d['최고기온'].notna()).astype(int)
        d.groupby(['시도', '날짜']).agg(
            평균기온=('평균기온', 'mean'), 평균기온_근사=('평균기온_근사', 'mean'), 최고기온=('최고기온', 'mean'),
            최저기온=('최저기온', 'mean'), 강수량=('강수량', 'mean'), 최대풍속=('최대풍속', 'mean'),
            최대순간풍속=('최대순간풍속', 'mean'), 평균습도=('평균습도', 'mean'), 일조시간=('일조시간', 'mean'),
            일사량=('일사량', 'mean'), 지점수_전체=('최고기온', 'count'), 지점수_ASOS=('n_ASOS', 'sum'),
            지점수_AWS=('n_AWS', 'sum'), 지점수_농업기상=('n_농업기상', 'sum')).round(2).reset_index().to_csv(
            agg / f'{y}_day.csv', index=False, encoding='utf-8-sig')
        d['연월'] = d['날짜'].str[:7]
        msum = lambda x: x.sum(min_count=1)
        d.groupby(['시도', '시군구', '관측망', '지점', '연월'], dropna=False).agg(
            월평균기온=('평균기온', 'mean'), 월평균기온_근사=('평균기온_근사', 'mean'), 월평균최고=('최고기온', 'mean'),
            월평균최저=('최저기온', 'mean'), 월최고극값=('최고기온', 'max'), 월최저극값=('최저기온', 'min'),
            월강수량=('강수량', msum), 월일조=('일조시간', msum), 월평균습도=('평균습도', 'mean'),
            고온일수=('고온일', 'sum'), 영하일수=('영하일', 'sum'), 강수일수=('강수일', 'sum'), 강풍일수=('강풍일', 'sum'),
            관측일=('최고기온', 'count'), 강수관측일=('강수량', 'count')).reset_index().to_csv(
            agg / f'{y}_stm.csv', index=False, encoding='utf-8-sig')
        (agg / f'{y}_stat.json').write_text(json.dumps({'ver': LINKVER, 'acc': acc, 'fills': fills, 'added': added, 'counts': counts, 'spat': spat},
                                                        ensure_ascii=False), encoding='utf-8')
        print(f'  연결 {y}: {len(D):,}행', flush=True)
    acc = {v: [0, 0, 0, 0.0, 0.0] for v in ['최고기온', '최저기온', '강수량', '최대풍속']}
    fills = {v: 0 for v in AWSV}; added = 0; counts = {}; spat = {}
    for y in years:
        st = json.loads((agg / f'{y}_stat.json').read_text(encoding='utf-8'))
        for v, a_ in st['acc'].items():
            b_ = acc[v]; b_[0] += a_[0]; b_[1] += a_[1]; b_[2] += a_[2]; b_[3] += a_[3]; b_[4] = max(b_[4], a_[4])
        for v, n in st['fills'].items():
            fills[v] += n
        added += st['added']
        for k, n in st.get('spat', {}).items():
            spat[k] = spat.get(k, 0) + n
        for k, n in st['counts'].items():
            counts[k] = counts.get(k, 0) + n
    pd.concat([pd.read_csv(agg / f'{y}_day.csv') for y in years]).to_csv(out / '시도별_일기상.csv', index=False, encoding='utf-8-sig')
    stm = pd.concat([pd.read_csv(agg / f'{y}_stm.csv', dtype={'지점': str}) for y in years], ignore_index=True)
    stm['일수'] = pd.to_datetime(stm['연월']).dt.days_in_month
    stm.round(2).to_csv(out / '지점별_월기상.csv', index=False, encoding='utf-8-sig')
    ok = stm[stm['관측일'] >= stm['일수'] * 0.8].copy()
    ok.loc[ok['강수관측일'] < ok['일수'] * 0.8, ['월강수량', '강수일수']] = np.nan
    for net in ('ASOS', 'AWS', '농업기상'):
        ok['n_' + net] = (ok['관측망'] == net).astype(int)
    for keys, name in ((['시도'], '시도별_월기상.csv'), (['시도', '시군구'], '시군구별_월기상.csv')):
        ok.groupby(keys + ['연월']).agg(
            월평균기온=('월평균기온', 'mean'), 월평균기온_근사=('월평균기온_근사', 'mean'),
            월평균최고=('월평균최고', 'mean'), 월평균최저=('월평균최저', 'mean'),
            월최고극값=('월최고극값', 'max'), 월최저극값=('월최저극값', 'min'),
            월강수량=('월강수량', 'mean'), 월일조=('월일조', 'mean'), 월평균습도=('월평균습도', 'mean'),
            고온일수=('고온일수', 'mean'), 영하일수=('영하일수', 'mean'), 강수일수=('강수일수', 'mean'),
            강풍일수=('강풍일수', 'mean'), 지점수_전체=('지점', 'nunique'), 지점수_ASOS=('n_ASOS', 'sum'),
            지점수_AWS=('n_AWS', 'sum'), 지점수_농업기상=('n_농업기상', 'sum')).round(2).reset_index().to_csv(
            out / name, index=False, encoding='utf-8-sig')
    cv = [{'항목': v, '비교행수(ASOS vs 같은지점 AWS일통계)': a[0], '완전일치율%': round(a[1] / a[0] * 100, 2) if a[0] else None,
           '0.5이내%': round(a[2] / a[0] * 100, 2) if a[0] else None, '평균절대차': round(a[3] / a[0], 3) if a[0] else None,
           '최대차': round(a[4], 1)} for v, a in acc.items()]
    pd.DataFrame(cv).to_csv(out / '교차검증.csv', index=False, encoding='utf-8-sig')
    rep['연결'] = {'관측망별_행': counts, '연도': [years[0], years[-1]], 'ASOS_빈항목_AWS로_보완': fills,
                 'ASOS지점_ASOS자료없는날_AWS로_추가': added, '공간이상_결측처리(시도·일 중앙값±15℃)': spat, '교차검증': cv,
                 '시군구_수': int(ok[['시도', '시군구']].drop_duplicates().shape[0])}
    return True


def main():
    here = pathlib.Path(__file__).resolve().parent
    dd = pathlib.Path(os.getenv('DATA_DIR') or 'data')
    dd = dd if dd.is_absolute() else here / dd
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default=str(dd / 'integrated'))
    ap.add_argument('--link', default='', help='03_연결 폴더 (기본: data/link)')
    ap.add_argument('--step', choices=['asos', 'aws', 'agri', 'prep', 'link', 'all'], default='all')
    ap.add_argument('--time-limit', type=int, default=0, help='초. 넘으면 연도 단위로 멈추고 다음 실행에서 이어함')
    a = ap.parse_args()
    LIMIT[0] = a.time_limit
    base = pathlib.Path(a.base)
    LINK[0] = pathlib.Path(a.link) if a.link else dd / 'link'
    rp = base / '전처리_점검.json'
    rep = json.loads(rp.read_text(encoding='utf-8')) if rp.exists() else {}
    rep['규칙'] = {
        '키': '날짜+관측망+지점 (지점은 문자: ASOS·AWS 숫자, 농업기상 10자리 코드)', '보간': '하지 않음',
        'ASOS': '2015~ API 전 항목, 2014 이전은 1991~2025 파일(엑셀본, 2014년까지만). 빈 날·빈 항목은 같은 지점 AWS일통계로 5항목 보완(출처·보완항목 열)',
        'AWS': '지상·AWS 일통계: 최고·최저기온, 강수량, 최대풍속, 최대순간풍속만',
        '농업기상': '농진청 농업기상 기본관측(V3) 2015~: 평균·최고·최저기온, 습도, 풍속, 강수, 일조, 일사, 결로시간, 초상·지중온도, 토양수분',
        '평균기온_근사': '(최고+최저)/2, 모든 지점 (AWS는 실제 평균기온 없음)',
        '강수': 'ASOS 2015~ -9.0 → 0(무강수 추정). AWS·농업기상은 값 그대로, 없으면 미관측',
        '범위점검': BOUNDS, '시도': 'ASOS·AWS 주소 → 없으면 최근접 주소지점 추정 / 농업기상은 지점명(시군구) 규칙',
        '월집계': '지점별 월 최고기온 관측일 80% 이상만 지역 평균에 포함(강수는 강수 관측일 80% 이상)'}
    done = True
    if a.step in ('asos', 'aws', 'agri', 'prep', 'all'):
        done = step_prep(base, rep, 'prep' if a.step == 'all' else a.step)
        rp.write_text(json.dumps(rep, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    if done and a.step in ('link', 'all'):
        print('3단계 연결', flush=True)
        done = step_link(base, rep)
        rp.write_text(json.dumps(rep, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    if not done:
        print('아직 남음 → 같은 명령 다시 실행'); return
    print(json.dumps({k: v for k, v in rep.items() if k != '규칙'}, ensure_ascii=False, indent=1, default=str)[:6000])
    print('완료')


if __name__ == '__main__':
    main()

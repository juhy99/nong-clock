# -*- coding: utf-8 -*-
"""ref/ 기준표 만들기 (조민철 PC에서 한 번, v3 단위가 바뀔 때만 다시). 2026-11-06
  python tools/make_ref.py <E:\\농산물 프로젝트\\분석용> <C:\\finalproject\\nong-clock> <관측지점_마스터.csv> <특보구역 wrn_reg 원본(.gz 또는 .txt, 없으면 생략)>
만드는 것: ref/region.csv market.csv item.csv variety_unit.csv variety_unit_code.csv grade_map.csv station.csv kamis_item.csv
"""
import gzip
import json
import re
import sys
from pathlib import Path

import pandas as pd

A, NC, ST = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
WRN = Path(sys.argv[4]) if len(sys.argv) > 4 else None
REF = Path(__file__).resolve().parents[1] / 'ref'
REF.mkdir(exist_ok=True)

# ── region (17 시·도) + 대표 지점(예보 격자용 도청·시청 근처 ASOS) ──
SIDO = [  # region_id, name, map_id(화면 지도 id), 대표 ASOS 지점
    (1, '서울', 'seoul', 108), (2, '부산', 'busan', 159), (3, '대구', 'daegu', 143), (4, '인천', 'incheon', 112), (5, '광주', 'gwangju', 156),
    (6, '대전', 'daejeon', 133), (7, '울산', 'ulsan', 152), (8, '세종', 'sejong', 239), (9, '경기', 'gyeonggi', 119), (10, '강원', 'gangwon', 101),
    (11, '충북', 'north-chungcheong', 131), (12, '충남', 'south-chungcheong', 177), (13, '전북', 'north-jeolla', 146),
    (14, '전남', 'south-jeolla', 165), (15, '경북', 'north-gyeongsang', 136), (16, '경남', 'south-gyeongsang', 155), (17, '제주', 'jeju', 184)]
st = pd.read_csv(ST, dtype={'지점': str})
asos = st[st['관측망'] == 'ASOS'].drop_duplicates('지점').set_index('지점')
reg = pd.DataFrame([{'region_id': i, 'name': n, 'map_id': m, 'rep_stn': s, 'rep_lat': asos.loc[str(s), '위도'], 'rep_lon': asos.loc[str(s), '경도']}
                    for i, n, m, s in SIDO])
reg.to_csv(REF / 'region.csv', index=False, encoding='utf-8-sig')
rid = dict(zip(reg.name, reg.region_id))

# ── station (ASOS 지점 → 시·도) ──
s = asos.reset_index()[['지점', '지점명', '위도', '경도', '시도', '시군구']].rename(columns={'지점': 'stn', '지점명': 'name', '위도': 'lat', '경도': 'lon', '시도': 'sido'})
s['region_id'] = s.sido.map(rid)
s.to_csv(REF / 'station.csv', index=False, encoding='utf-8-sig')

# ── market (팀 shared/markets.json 32곳 = 화면에 보임 + 정산 코드표에 있는 나머지) ──
mj = json.loads((NC / 'shared' / 'markets.json').read_text(encoding='utf-8'))['markets']
m = pd.DataFrame([{'market_code': x['code'], 'name': x['name'], 'region_id': rid.get(x['sido']), 'sigungu': x.get('sigungu', ''),
                   'lat': x.get('lat'), 'lon': x.get('lon'), 'is_active': True} for x in mj])
m = pd.concat([pd.DataFrame([{'market_code': 'national', 'name': '전국', 'region_id': None, 'sigungu': '', 'lat': None, 'lon': None, 'is_active': True}]), m])
m.to_csv(REF / 'market.csv', index=False, encoding='utf-8-sig')

# ── item (v3 50품목) ──
P = A / '00_기본자료' / '02_전처리' / '103_상위품목_품종목록_물량금액'
v = pd.read_csv(P / '05_상위50_예측단위_v3.csv')
M = pd.read_csv(A / '26_품종구분_전처리_변수' / '02_구분_시계열' / '01_구분매핑표.csv', dtype=str)
V = pd.read_csv(P / '02_품종작형_목록.csv', dtype=str)
ij = json.loads((NC / 'shared' / 'items.json').read_text(encoding='utf-8'))
(REF / 'items.json').write_text(json.dumps({'index_groups': ij.get('index_groups', [])}, ensure_ascii=False, indent=1), encoding='utf-8')
by4 = {x['code4']: x for x in ij['items']}
code4_of = V.dropna(subset=['계열키']).groupby('품목명')['계열키'].agg(lambda z: z.str[:4].value_counts().index[0]).to_dict()
for n, c in M.dropna(subset=['품목명']).drop_duplicates('품목명')[['품목명', '품목코드4']].values:
    code4_of.setdefault(n, c)  # 품종 계열이 없는 품목(새송이·열무·쪽파 등)은 매핑표 품목명으로
items = v.groupby('품목명', sort=False).agg(물량순위=('물량순위', 'first'), 물량=('연평균_물량_t', 'sum')).reset_index().sort_values('물량순위')
rows = []
for r in items.itertuples():
    c4 = code4_of.get(r.품목명, '')
    j = by4.get(c4, {})
    kam = M[(M.품목코드4 == c4) & M.KAMIS품목코드.notna()].KAMIS품목코드.unique()
    rows.append({'item_code': j.get('code') or f'item_{c4}', 'code4': c4, 'name': r.품목명, 'category': j.get('category', ''),
                 'emoji': j.get('emoji') or '', 'kamis_code': kam[0] if len(kam) else '', 'sort_order': int(r.물량순위)})
it = pd.DataFrame(rows)
it.to_csv(REF / 'item.csv', index=False, encoding='utf-8-sig')
print('item', len(it), '/ items.json 에 없는 code4:', it[it.item_code.str.startswith('item_')].code4.tolist())

# ── variety_unit + 단위별 공영 품종코드·달 ──
SEA = {'봄': [3, 4, 5], '여름': [6, 7, 8], '가을': [9, 10, 11], '겨울': [12, 1, 2]}
cl = lambda x: re.sub(r'[\s()·,]', '', str(x))
key = {(r.품목명, cl(r.계열)): r.계열키 for r in V.itertuples() if isinstance(r.계열키, str)}
codes_of_key = M.groupby('계열키').apply(lambda g: sorted(g.품종코드.unique())).to_dict()
all_codes = M.groupby('품목코드4').품종코드.apply(lambda z: sorted(z.unique())).to_dict()
units, ucode = [], []
uid = 0
for itn, g in v.groupby('품목명', sort=False):
    c4 = code4_of.get(itn, '')
    named = g[g.묶음 != '품목(기타) 세분']
    used = set()
    for r in named.itertuples():
        uid += 1
        names = [n for n in re.split(r'[·,]', str(r.들어간_품종)) if n.strip() and n.strip() != 'nan']
        cs = sorted({c for n in names for c in codes_of_key.get(key.get((itn, cl(n)), ''), [])})
        used |= set(cs)
        units.append({'unit_id': uid, 'unit_name': r.예측단위, 'item_code4': c4, 'unit_kind': r.묶음, 'variety_names': '·'.join(names),
                      'months': '', 'cultivation': r.재배방식_추정 if isinstance(r.재배방식_추정, str) else '',
                      'origin_type': r.품목_산지판정, 'avg_volume_t': round(r.연평균_물량_t, 1), 'is_active': True, 'code_count': len(cs)})
        ucode += [{'unit_id': uid, 'code4': c4, 'variety_code': c, 'months': ''} for c in cs]
    etc = g[g.묶음 == '품목(기타) 세분']
    rest = [c for c in all_codes.get(c4, []) if c not in used]
    seasons_named = {se for se in SEA for n in etc.예측단위 if f'기타·{se}' in n}
    for r in etc.itertuples():
        uid += 1
        se = next((x for x in SEA if f'기타·{x}' in r.예측단위), None)
        mon = SEA[se] if se else sorted(m for x in SEA if x not in seasons_named for m in SEA[x]) if '그 외' in r.예측단위 else list(range(1, 13))
        reg_ = re.search(r'·[^·]+ (\S+)\)$', r.예측단위)
        units.append({'unit_id': uid, 'unit_name': r.예측단위, 'item_code4': c4, 'unit_kind': r.묶음, 'variety_names': '이름 없는 물량·이름 있는 단위에 안 든 품종',
                      'months': ','.join(map(str, mon)), 'cultivation': r.재배방식_추정 if isinstance(r.재배방식_추정, str) else '',
                      'origin_type': r.품목_산지판정, 'avg_volume_t': round(r.연평균_물량_t, 1), 'is_active': True, 'code_count': len(rest),
                      'main_region': reg_.group(1) if reg_ else ''})
        ucode += [{'unit_id': uid, 'code4': c4, 'variety_code': c, 'months': ','.join(map(str, mon))} for c in rest]
U = pd.DataFrame(units)
U['main_region_id'] = U.get('main_region', pd.Series(dtype=str)).map(rid)
U.to_csv(REF / 'variety_unit.csv', index=False, encoding='utf-8-sig')
pd.DataFrame(ucode).to_csv(REF / 'variety_unit_code.csv', index=False, encoding='utf-8-sig')
print('variety_unit', len(U), '/ 품종코드 0개인 단위', int((U.code_count == 0).sum()), U[U.code_count == 0].unit_name.tolist()[:20])

# ── grade_map (원장 등급명 → 화면 등급) ──
G = {'특': 'SPECIAL', '상': 'HIGH', '중': 'MID', '보통': 'MID', '하': 'LOW', '등외': 'LOW', '5등': 'LOW', '6등': 'LOW', '7등': 'LOW', '8등': 'LOW',
     '상품': 'HIGH', '중품': 'MID', '하품': 'LOW'}
pd.DataFrame([{'source': 'ledger' if k not in ('상품', '중품', '하품') else 'kamis', 'raw_grade': k, 'grade': g} for k, g in G.items()]).to_csv(
    REF / 'grade_map.csv', index=False, encoding='utf-8-sig')

# ── KAMIS 품목코드 → 공영 code4 ──
km = M.dropna(subset=['KAMIS품목코드'])[['KAMIS품목코드', 'KAMIS품목명', '품목코드4']].drop_duplicates('KAMIS품목코드')
km.columns = ['kamis_code', 'kamis_name', 'code4']
km.to_csv(REF / 'kamis_item.csv', index=False, encoding='utf-8-sig')

# ── 가락 경매전·후 품목 → 품목 (15번 03_품목대응표: 가락물량_코드 앞 4자리 = 공영 품목코드) ──
gf = A / '00_기본자료' / '02_전처리' / '15_가락시장_경매전후_반입물량' / '03_품목대응표.csv'
if gf.exists():
    g = pd.read_csv(gf, dtype=str)
    g['code4'] = g.가락물량_코드.fillna('').str.split('|').str[0].str.strip().str[:4]
    g['item_code'] = g.code4.map(dict(zip(it.code4, it.item_code))).fillna('')
    pd.DataFrame({'before_name': g.경매전_원문명.fillna(''), 'after_code': g.경매후_품목코드.fillna(''), 'garak_name': g.품목명,
                  'code4': g.code4, 'item_code': g.item_code, 'before_meaning': g.경매전_성격.fillna('')}).to_csv(REF / 'garak_item.csv', index=False, encoding='utf-8-sig')

# ── 특보구역 표 (있으면 미리 넣어 둠. 없어도 수집기가 처음에 받음) ──
if WRN and WRN.exists():
    b = gzip.open(WRN).read() if WRN.suffix == '.gz' else WRN.read_bytes()
    t = b.decode('utf-8', 'replace')
    for e in ('utf-8', 'cp949', 'euc-kr'):
        try:
            t = b.decode(e); break
        except UnicodeDecodeError:
            continue
    (REF / 'wrn_reg.txt').write_text(t, encoding='utf-8')
print('ref 완료:', sorted(p.name for p in REF.iterdir()))

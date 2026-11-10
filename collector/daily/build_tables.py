# -*- coding: utf-8 -*-
"""data/raw → DB 테이블 모양 CSV (data/tables/<테이블>.csv). 2026-11-06
  python build_tables.py                  # 최근 14일치만 다시 만듦 (매일 실행용, load_db.py 가 upsert)
  python build_tables.py --since 2020-01-01   # 과거 전부 (처음 한 번)
  python build_tables.py --only price_daily weather_daily
열 이름은 schema.sql 과 같다. 가격은 원/kg 정수.
"""
import argparse
import csv
import datetime as dt
import glob
import gzip
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

import common as C

REF = C.REF
OUT = C.OUT
RAW = C.RAW


def ref(name, **kw):
    df = pd.read_csv(REF / f'{name}.csv', dtype=str, keep_default_na=False, **kw)
    for c in df.columns:
        if c.endswith('region_id'):
            df[c] = df[c].str.replace(r'\.0$', '', regex=True)  # 1.0 → 1 (DB 의 SMALLINT)
    return df


def save(df, name, first=True):
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT / f'{name}.csv', index=False, encoding='utf-8', mode='w' if first else 'a', header=first)
    print(f'  {name}: {len(df):,}행' + ('' if first else ' (이어 씀)'), flush=True)


HIST = C.DATA / 'hist'


def upsert_hist(df, name, keys):
    """지수·시장 계수·휴장 판단에 쓰는 긴 기록 (전국·시장 ALL 단가). 매일 최근분만 덮어씀"""
    HIST.mkdir(parents=True, exist_ok=True)
    f = HIST / f'{name}.csv'
    if f.exists():
        old = pd.read_csv(f, dtype={'market_code': str, 'code4': str, 'ym': str})  # code4 '0601' 의 앞 0 이 지워지지 않게
        old = old[~old.set_index(keys).index.isin(df.set_index(keys).index)]
        df = pd.concat([old, df])
    df.sort_values(keys).to_csv(f, index=False, encoding='utf-8')


def pg_array(xs):
    return '{' + ','.join(str(x) for x in xs) + '}'


# ───────────── 기준표 ─────────────
def t_refs():
    reg = ref('region')
    save(reg[['region_id', 'name', 'map_id']], 'region')
    m = ref('market')
    save(m[['market_code', 'name', 'region_id', 'sigungu', 'lat', 'lon', 'is_active']], 'market')
    it = ref('item')
    ij = json.loads((REF / 'items.json').read_text(encoding='utf-8')) if (REF / 'items.json').exists() else {}
    grp = {c: g['code'] for g in ij.get('index_groups', []) for c in g.get('categories', [])}
    it['index_group'] = it.category.map(grp).fillna('')
    save(it[['item_code', 'code4', 'name', 'category', 'index_group', 'emoji', 'kamis_code', 'sort_order']], 'item')
    if ij.get('index_groups'):
        save(pd.DataFrame([{'group_code': g['code'], 'name': g['name'], 'emoji': g.get('emoji', ''), 'categories': pg_array(g.get('categories', []))}
                           for g in ij['index_groups']] + [{'group_code': 'all', 'name': '전체', 'emoji': '📊', 'categories': '{}'}]), 'index_group')
    u = ref('variety_unit')
    uc = ref('variety_unit_code')
    code = dict(zip(it.code4, it.item_code))
    u['item_code'] = u.item_code4.map(code)
    u['variety_codes'] = u.unit_id.map(uc.groupby('unit_id').variety_code.apply(pg_array)).fillna('{}')
    u['months'] = u.months.map(lambda s: pg_array(s.split(',')) if s else '')
    save(u[['unit_id', 'unit_name', 'item_code', 'unit_kind', 'variety_codes', 'variety_names', 'months', 'main_region_id',
            'cultivation', 'origin_type', 'avg_volume_t', 'is_active']], 'variety_unit')
    save(ref('grade_map'), 'grade_map')


# ───────────── 경매 원장 → 시세 ─────────────
SIDO_RULES = [('서울', '서울'), ('부산', '부산'), ('대구', '대구'), ('인천', '인천'), ('광주', '광주'), ('대전', '대전'), ('울산', '울산'),
              ('세종', '세종'), ('경기', '경기'), ('강원', '강원'), ('충청북', '충북'), ('충북', '충북'), ('충청남', '충남'), ('충남', '충남'),
              ('전라북', '전북'), ('전북', '전북'), ('전남광주', None), ('전라남', '전남'), ('전남', '전남'), ('경상북', '경북'), ('경북', '경북'),
              ('경상남', '경남'), ('경남', '경남'), ('제주', '제주')]


def origin_region(name):
    """산지명 → 시·도 이름. 2026 '전남광주통합특별시'는 다음 낱말이 광주 자치구면 광주, 아니면 전남. 나라 이름·수입산 → 수입"""
    s = str(name).strip()
    if not s or s in ('.', 'nan'):
        return None, False
    w = s.split()
    for pre, sd in SIDO_RULES:
        if w[0].startswith(pre):
            if sd is None:
                return ('광주' if len(w) > 1 and w[1] in ('광주광역시', '동구', '서구', '남구', '북구', '광산구') else '전남'), False
            return sd, False
    return None, True  # 나라 이름·수입산


def drop_double_feeds(day):
    """원장에 같은 날·시장·법인 거래가 통째로 두 번 들어간 경우 한 벌만 남김 (11-10).
    예: 2024-04-26~30 210009·230003 등 시장 하루치 전체, 2020 년 여러 날 (원본 점검표 01_원본/경매원장_공영_원본/00_점검.csv 의 '통째중복').
    기준: 시장·법인·하루 묶음에서 모든 칸이 같은 줄의 비율이 0.2 이상이면 그 묶음의 똑같은 줄을 하나만 남김.
    근거(정하기 전에 본 분포): 2024-04 묶음 2,167개 중 0.9 이상 163개(통째 두 번), 0.2~0.5 4개(240004 한 법인 일부 두 번), 0.05~0.2 1개,
    나머지는 0.05 미만. 2025-05 는 0.05 이상이 하나도 없음 → 0.05 미만의 똑같은 줄은 진짜로 똑같은 거래로 보고 그대로 둠"""
    if day.empty or '법인_공판장코드' not in day:
        return day, 0
    dup = day.duplicated(keep=False)
    share = dup.groupby([day['도매시장코드'], day['법인_공판장코드']]).transform('mean')
    drop = day.duplicated(keep='first') & (share >= 0.2)
    return day[~drop], int(drop.sum())


def read_auction(since, until=None):
    # until(그 날 앞까지)을 주면 그 달 파일만 읽는다. 없으면 since 뒤 전부 → 달마다 부를 때 전 기간을 다시 읽어 메모리가 터짐 (11-09 고침)
    lo, hi = since.strftime('%Y%m%d'), (until.strftime('%Y%m%d') if until else '99999999')
    files = sorted(f for f in glob.glob(str(RAW / 'auction' / '*.csv.gz')) if lo <= Path(f).name[:8] < hi)
    cols = ['정산일자', '도매시장코드', '대분류코드', '중분류코드', '소분류코드', '단위중량', '단위코드', '등급명', '산지명', '총물량', '총금액', '최저가', '최고가']
    parts, dropped = [], 0
    for f in files:
        try:
            day = pd.read_csv(f, dtype=str, compression='gzip')  # 하루 파일 = 정산일자 하나. 모든 칸으로 중복을 봐야 해서 통째로 읽음
            day, n = drop_double_feeds(day)
            dropped += n
            parts.append(day[cols])
        except (ValueError, EOFError, KeyError) as e:
            print('  읽기 실패', f, e)
    if dropped:
        print(f'  통째 중복으로 뺀 줄: {dropped:,}', flush=True)
    if not parts:
        return pd.DataFrame(columns=cols)
    a = pd.concat(parts, ignore_index=True)
    a['date'] = pd.to_datetime(a.정산일자.str[:8], format='%Y%m%d').dt.date.astype(str)
    a['code4'] = a.대분류코드.str.zfill(2) + a.중분류코드.str.zfill(2)
    a['variety_code'] = a.소분류코드.str.zfill(2)
    for c in ('단위중량', '총물량', '총금액', '최저가', '최고가'):
        a[c] = pd.to_numeric(a[c], errors='coerce')
    a = a[(a.총물량 > 0) & (a.총금액 > 0)]
    return a


def _wmed(df, keys):
    """금액 가중 중앙값(원/kg): 거래 금액의 절반이 이 값 이하에서 거래됨"""
    d = df[keys + ['up', '총금액']].sort_values(keys + ['up'])
    c = d.groupby(keys).총금액.cumsum(); t = d.groupby(keys).총금액.transform('sum')
    return d[c >= t / 2].groupby(keys).up.first()


def drop_entry_errors(a):
    """원장 입력 오류 거르기 (11-09). 예: 감귤 '800kg 상자' 211t 11원/kg, 열무 '60201kg 상자', 감자 '0.1kg 상자' 0.5kg 98만원/kg.
    무게(단위중량·총물량)가 틀리고 금액은 맞는 경우가 대부분이라, 기준은 '금액 가중 중앙값'(무게 오류 줄이 기준을 끌지 못함).
    같은 달(이 함수는 달 묶음마다 불림) 같은 품목·품종의 금액 가중 중앙값, 그 달 거래 10건 미만 품종은 품목 값.
    1kg 값이 기준의 1/10 미만이거나 10배 초과면 뺌 — 2025-08·2026-06 기준 물량의 0.3~0.6%, 금액의 0.05~0.1%.
    알려진 부작용: 진짜 거래일 수 있는 아주 싼 줄도 빠짐 (예: 2026-06 사과 가공용으로 보이는 300원/kg, 그 달 사과 물량의 약 4%)"""
    keys = ['code4', 'variety_code']
    ref = a.join(_wmed(a, keys).rename('_rv'), on=keys)._rv
    n = a.groupby(keys).up.transform('size')
    ref = ref.where(n >= 10, a.code4.map(_wmed(a, ['code4'])))
    ok = (a.up >= ref / 10) & (a.up <= ref * 10)
    return a[ok].copy()


def _prices_chunk(a, first, hist):
    it = ref('item')
    a = a[a.code4.isin(it.code4)]
    if a.empty:
        return
    a['item_code'] = a.code4.map(dict(zip(it.code4, it.item_code)))
    gm = ref('grade_map'); gm = dict(zip(gm[gm.source == 'ledger'].raw_grade, gm[gm.source == 'ledger'].grade))
    a['grade'] = a.등급명.str.strip().map(gm)
    a['up'] = a.총금액 / a.총물량   # 거래 줄마다 원/kg (최고·최저가 칸은 포장 단위라 품목마다 기준이 달라 안 씀)
    a = drop_entry_errors(a)
    a['market_code'] = a.도매시장코드.str.strip()

    def agg(df, keys, hilo=False):
        g = df.groupby(keys, as_index=False).agg(volume_kg=('총물량', 'sum'), amount_won=('총금액', 'sum'))
        if hilo:
            q = df.sort_values('up').groupby(keys)
            df2 = df.sort_values('up').assign(cw=q.총물량.cumsum(), tw=q.총물량.transform('sum'))
            df2['pos'] = df2.cw / df2.tw
            lo = df2[df2.pos >= 0.1].groupby(keys).up.first().rename('price_low')
            hi = df2[df2.pos >= 0.9].groupby(keys).up.first().rename('price_high')
            g = g.merge(lo.reset_index(), on=keys, how='left').merge(hi.reset_index(), on=keys, how='left')
        g['price'] = (g.amount_won / g.volume_kg).round().astype('Int64')
        for c in ('price_high', 'price_low'):
            if c in g:
                g[c] = g[c].round().astype('Int64')
        g['volume_kg'] = g.volume_kg.round(1); g['amount_won'] = g.amount_won.round()
        return g
    base = ['date', 'market_code', 'item_code']
    # 산지(시·도) · 수입 여부 — 도매 시세(price_daily)는 국산만 (11-09: 수입품이 섞이면 시장 단가가 흔들리고 예측 모델 기준(국산)과 달라짐)
    #   수입 물량·단가는 출하지역 표(price_origin_daily)의 '수입' 줄에 그대로 남음
    rid = dict(zip(ref('region').name, ref('region').region_id))
    oo = a.산지명.map(origin_region)
    a['origin_region_id'] = [rid.get(s) if s else ('0' if imp else None) for s, imp in oo]
    a['is_import'] = [imp for _, imp in oo]
    a_all = a
    a = a[~a.is_import]
    nat = a.assign(market_code='national')
    pd_ = pd.concat([agg(a[a.grade.notna()], base + ['grade'], True), agg(a, base, True).assign(grade='ALL'),
                     agg(nat[nat.grade.notna()], base + ['grade'], True), agg(nat, base, True).assign(grade='ALL')])
    save(pd_[base + ['grade', 'volume_kg', 'amount_won', 'price', 'price_high', 'price_low']], 'price_daily', first)
    hist.append(pd_[pd_.grade == 'ALL'][base + ['volume_kg', 'price']].copy())

    a = a_all[a_all.origin_region_id.notna()]
    keys = base + ['origin_region_id', 'is_import']
    po = pd.concat([agg(a, keys), agg(a.assign(market_code='national'), keys)])
    save(po[keys + ['volume_kg', 'amount_won', 'price']], 'price_origin_daily', first)

    # 품종 단위 (전국, 국산만): 단위의 품종코드 + 달
    uc = ref('variety_unit_code')
    uc['months'] = uc.months.map(lambda s: [int(x) for x in s.split(',')] if s else list(range(1, 13)))
    uc = uc.explode('months').rename(columns={'months': 'month'})
    dom = a[~a.is_import].copy()
    dom['month'] = pd.to_datetime(dom.date).dt.month
    j = dom.merge(uc, on=['code4', 'variety_code', 'month'], how='inner')
    pu = agg(j.assign(market_code='national'), ['date', 'unit_id'])
    save(pu[['date', 'unit_id', 'volume_kg', 'amount_won', 'price']], 'price_unit_daily', first)
    return j.총물량.sum(), dom.총물량.sum()


def t_prices(since):
    """원장을 달마다 읽어 이어 씀 (2020년부터 전부 만들 때도 메모리 걱정 없게)"""
    m = since.replace(day=1)
    hist, first, inu, dom = [], True, 0, 0
    while m <= C.today():
        nxt = (m.replace(day=28) + dt.timedelta(4)).replace(day=1)
        a = read_auction(max(m, since), nxt)
        a = a[a.date < nxt.isoformat()]
        if not a.empty:
            r = _prices_chunk(a, first, hist)
            if r:
                inu += r[0]; dom += r[1]
            first = False
        m = nxt
    if first:
        print('  공영도매 원자료 없음 (collect.py auction 먼저)'); return
    upsert_hist(pd.concat(hist), 'price_all', ['date', 'market_code', 'item_code'])
    print(f'    품종 단위에 들어간 국산 물량 비율: {inu / max(dom, 1):.3f}')


def t_index(since):
    """홈 지수: 품목 전국 단가 ÷ 그 품목 직전 365일 평균 × 100 을 묶음 안에서 평균 (평소 = 100). price_daily(전국·ALL) 전체 기간이 필요"""
    f = HIST / 'price_all.csv'
    if not f.exists():
        return
    p = pd.read_csv(f, dtype={'market_code': str})
    p = p[p.market_code == 'national'][['date', 'item_code', 'price']].copy()
    p['date'] = pd.to_datetime(p.date)
    p = p.sort_values(['item_code', 'date'])
    p = p.reset_index(drop=True)
    p['base'] = pd.concat([g.set_index('date').price.rolling('365D', min_periods=60).mean().shift(1).reset_index(drop=True).set_axis(g.index)
                           for _, g in p.groupby('item_code')]).sort_index()
    p['ratio'] = p.price / p.base * 100
    it = pd.read_csv(OUT / 'item.csv', dtype=str)
    p['group_code'] = p.item_code.map(dict(zip(it.item_code, it.index_group)))
    p = p.dropna(subset=['ratio'])
    if p.empty:
        print('  price_index_daily: 기준(직전 365일 중 60일 이상)이 아직 없음 → 과거 원장을 먼저 채우세요'); return
    g = pd.concat([p, p.assign(group_code='all')]).groupby(['date', 'group_code']).agg(value=('ratio', 'mean'), item_count=('ratio', 'size')).reset_index()
    g['value'] = g.value.astype(float).round(2); g['date'] = g.date.dt.date.astype(str)
    save(g[g.date >= str(since)], 'price_index_daily')


def t_market_factor():
    """시장 계수: 그 시장 단가 ÷ 전국 단가의 품목·달 중앙값 (최근 3년, 10일 이상). 시장별 예측 = 전국 예측 × 계수"""
    f = HIST / 'price_all.csv'
    if not f.exists():
        return
    p = pd.read_csv(f, dtype={'market_code': str})
    p['date'] = pd.to_datetime(p.date)
    p = p[p.date >= p.date.max() - pd.Timedelta(days=3 * 365)]
    n = p[p.market_code == 'national'][['date', 'item_code', 'price']].rename(columns={'price': 'nat'})
    m = p[p.market_code != 'national'].merge(n, on=['date', 'item_code'])
    m['r'] = m.price / m.nat; m['month'] = m.date.dt.month
    g = m.groupby(['item_code', 'market_code', 'month']).agg(factor=('r', 'median'), days=('r', 'size')).reset_index()
    g = g[g.days >= 10]
    g['factor'] = g.factor.round(4)
    g['period'] = f'{p.date.min():%Y-%m}~{p.date.max():%Y-%m}'
    save(g, 'market_factor')


# ───────────── KAMIS 소매 ─────────────
def per_kg(unit):
    s = str(unit).replace(' ', '')
    m = re.fullmatch(r'([\d.]+)(kg|g)', s)
    if not m:
        return None
    v = float(m.group(1))
    return v if m.group(2) == 'kg' else v / 1000


# ───────────── 1개(포기)당 무게 (11-10): KAMIS 소매가가 '1포기·10개' 단위인 품목을 원/kg 으로 바꾸는 데 씀 ─────────────
PIECE_MIN = 30   # 품목·달 줄이 이보다 적으면 그 품목 1년 전체 값, 그것도 적으면 환산 안 함
# 11-10 사후 추가: 크기명 2·11·12·21·22개는 품목과 상관없이 몰려 나오고(크기 코드로 보임) 무게가 안 맞음
#   예) 오이 10kg '11개' = 1개 0.9kg, 감귤 5kg '21개', 사과 10kg '11개' → 빼고 계산
PIECE_CODE_LIKE = {2, 11, 12, 21, 22}
# 11-10 사후 추가 2: 그래도 사과 여름 2kg·가지 3.3kg·수박 1~2kg 처럼 안 맞는 품목이 남음 → 12달 값의 최대 ÷ 최소가
#   이 값 이하인 품목만 환산에 씀 (배추·무·양배추·호박·배·메론·참외 → 참외는 아래 3에서 뺌). 틀린 소매가보다 빈칸이 나음
PIECE_STABLE = 1.5
# 11-10 사후 추가 3: 참외(0802)는 환산하면 소매가 < 도매가인 날이 286일 중 78일 → 1개당 무게(0.5kg)가 너무 무거운 것으로 보고 뺌
PIECE_EXCLUDE = {'0802'}


def piece_rows(m, nxt):
    """한 달 원장에서 크기명이 정확히 'N개' 인 국산 줄 → (code4, 달, 1개당 kg, 물량). 통째 중복은 먼저 뺌"""
    lo, hi = m.strftime('%Y%m%d'), nxt.strftime('%Y%m%d')
    files = sorted(f for f in glob.glob(str(RAW / 'auction' / '*.csv.gz')) if lo <= Path(f).name[:8] < hi)
    it = set(ref('item').code4); parts = []
    for f in files:
        try:
            day, _ = drop_double_feeds(pd.read_csv(f, dtype=str, compression='gzip'))
        except (ValueError, EOFError, KeyError) as e:
            print('  읽기 실패', f, e); continue
        day['code4'] = day.대분류코드.str.strip().str.zfill(2) + day.중분류코드.str.strip().str.zfill(2)
        n = pd.to_numeric(day.크기명.str.strip().str.extract(r'^(\d+)개$')[0], errors='coerce')
        w = pd.to_numeric(day.단위중량, errors='coerce'); v = pd.to_numeric(day.총물량, errors='coerce')
        ok = day.code4.isin(it) & n.between(1, 500) & (w > 0) & (v > 0)
        ok &= ~day.산지명.map(lambda x: origin_region(x)[1])
        d = pd.DataFrame({'code4': day.code4[ok], 'n': n[ok].astype(int), 'kg': (w[ok] / n[ok]).round(3), 'vol': v[ok]})
        if not d.empty:
            parts.append(d)
    if not parts:
        return None
    d = pd.concat(parts)
    g = d.groupby(['code4', 'n', 'kg'], as_index=False).agg(vol=('vol', 'sum'), rows=('vol', 'size'))
    return g.assign(ym=m.strftime('%Y-%m'))


def _wmed_kg(g):
    g = g.groupby('kg', as_index=False).vol.sum().sort_values('kg')
    c = g.vol.cumsum()
    return float(g.kg[c >= g.vol.sum() / 2].iloc[0])


def piece_weight_table():
    """hist/piece_rows.csv(달마다 쌓인 줄) → hist/piece_weight.csv: 품목 × 달(1~12)의 물량 가중 중앙값.
    달 줄 < PIECE_MIN 이면 그 품목 1년 전체 값(basis=year), 그것도 < PIECE_MIN 이면 뺌"""
    f = HIST / 'piece_rows.csv'
    if not f.exists():
        return None
    r = pd.read_csv(f, dtype={'code4': str, 'ym': str})
    r['month'] = r.ym.str[5:7].astype(int)
    r = r[~r.n.isin(PIECE_CODE_LIKE)]
    out = []
    for c4, g in r.groupby('code4'):
        if g.rows.sum() < PIECE_MIN:
            continue
        year = _wmed_kg(g)
        for mo in range(1, 13):
            gm = g[g.month == mo]
            if gm.rows.sum() >= PIECE_MIN:
                out.append((c4, mo, _wmed_kg(gm), 'month', int(gm.rows.sum())))
            else:
                out.append((c4, mo, year, 'year', int(g.rows.sum())))
    pw = pd.DataFrame(out, columns=['code4', 'month', 'kg_per_piece', 'basis', 'rows'])
    spread = pw.groupby('code4').kg_per_piece.agg(lambda x: x.max() / x.min())
    pw['use'] = pw.code4.map(spread <= PIECE_STABLE) & ~pw.code4.isin(PIECE_EXCLUDE)
    pw.to_csv(HIST / 'piece_weight.csv', index=False, encoding='utf-8')
    return pw


def t_piece_weight(since, until=None):
    """since 가 든 달부터 (until 앞 달까지) 원장을 다시 읽어 hist/piece_rows.csv 를 그 달만 덮어씀 → piece_weight.csv 다시 계산.
    매일 실행(최근 14일)이면 이번 달·지난 달만 다시 읽음"""
    m = since.replace(day=1); end = until or C.today()
    rows = []
    while m <= end:
        nxt = (m.replace(day=28) + dt.timedelta(4)).replace(day=1)
        g = piece_rows(m, nxt)
        if g is not None:
            rows.append(g)
        m = nxt
    if rows:
        upsert_hist(pd.concat(rows), 'piece_rows', ['code4', 'ym', 'n', 'kg'])
    pw = piece_weight_table()
    print(f'  1개당 무게: {0 if pw is None else pw.code4.nunique()}품목', flush=True)


def per_piece(unit):
    """KAMIS 단위 '10개' · '1포기' → 개수. 아니면 None"""
    m = re.fullmatch(r'(\d+)(개|포기)', str(unit).replace(' ', ''))
    return int(m.group(1)) if m else None


def t_retail(since):
    files = sorted(f for f in glob.glob(str(RAW / 'kamis' / '*.csv')) if Path(f).stem >= since.strftime('%Y%m%d'))
    if not files:
        return
    k = pd.concat([pd.read_csv(f, dtype=str) for f in files])
    k = k[(k.가격구분 == '소매') & k.가격.notna()]
    km = ref('kamis_item'); it = ref('item')
    k['code4'] = k.품목코드.map(dict(zip(km.kamis_code, km.code4)))
    k['item_code'] = k.code4.map(dict(zip(it.code4, it.item_code)))
    k = k[k.item_code.notna()].copy()
    k['kg'] = k.단위.map(per_kg)
    # '1포기·10개' 단위 (11-10): 개수 × 원장에서 구한 그 품목·달의 1개당 kg (piece_weight) 으로 바꿈. 환산값이라 source_spec 에 적음
    k['note'] = ''
    pf = HIST / 'piece_weight.csv'
    if pf.exists():
        pw = pd.read_csv(pf, dtype={'code4': str})
        pw = pw[pw.use]
        pw = dict(zip(zip(pw.code4, pw.month), pw.kg_per_piece))
        pcs = k.단위.map(per_piece)
        mo = pd.to_numeric(k.조회일자.str[5:7], errors='coerce')
        kp = pd.Series([pw.get((c, m)) for c, m in zip(k.code4, mo)], index=k.index, dtype=float)
        use = k.kg.isna() & pcs.notna() & kp.notna()
        k.loc[use, 'kg'] = pcs[use] * kp[use]
        k.loc[use, 'note'] = ' · 1개≈' + kp[use].map(lambda x: f'{x:g}') + 'kg 환산'
    k = k[k.kg.notna() & (k.kg > 0)]
    k['price'] = (pd.to_numeric(k.가격, errors='coerce') / k.kg).round()
    k['rank_order'] = k.등급.map({'상품': 0, '중품': 1}).fillna(2)
    # 품목마다 규격 하나로 고정 (11-09): 날마다 첫 규격을 고르면 포도가 샤인머스켓↔캠벨얼리로 바뀌어 값이 튐
    # → 가장 좋은 등급 중 조사일이 가장 많은 (품종코드, 단위) 하나만 씀
    best = k[k.rank_order == k.groupby('item_code').rank_order.transform('min')]
    spec = best.groupby(['item_code', '품종코드', '단위']).조회일자.nunique().reset_index().sort_values(['item_code', '조회일자'], ascending=[True, False]).drop_duplicates('item_code')
    k = k.merge(spec[['item_code', '품종코드', '단위']], on=['item_code', '품종코드', '단위'])
    k = k.sort_values(['조회일자', 'item_code', 'rank_order'])
    r = k.drop_duplicates(['조회일자', 'item_code'])
    r = r.assign(date=r.조회일자, source_spec=r.품종명 + ' · ' + r.등급 + ' · ' + r.단위 + r.note, price=r.price.astype('Int64'))
    save(r[['date', 'item_code', 'price', 'source_spec']], 'retail_price_daily')


# ───────────── 날씨 (팀 날씨 수집기 결과: data/weather/site/날씨_대통합_일별.csv) ─────────────
WX_SITE = C.DATA / 'weather' / 'site' / '날씨_대통합_일별.csv'


def read_wx():
    if not WX_SITE.exists():
        print(f'  날씨 대통합 없음: {WX_SITE} (collect.py weather 먼저)'); return None
    w = pd.read_csv(WX_SITE, encoding='utf-8-sig', low_memory=False)
    w = w[w.구분 == '시도_일'].copy()
    w['region_id'] = w.시도.map(dict(zip(ref('region').name, ref('region').region_id)))
    return w[w.region_id.notna()]


def t_weather(since):
    """시·도 일별: ASOS+AWS+농업기상 관측소 평균 (팀 기상 통합 전처리 값 그대로)"""
    w = read_wx()
    if w is None:
        return
    w = w[w.날짜 >= str(since)]
    g = pd.DataFrame({'date': w.날짜, 'region_id': w.region_id, 'temp_avg': w.평균기온.fillna(w.평균기온_근사), 'temp_min': w.최저기온,
                      'temp_max': w.최고기온, 'rain_mm': w.강수량, 'sun_hr': w.일조시간, 'humidity': w.평균습도, 'wind': w.최대풍속})
    g[g.columns[2:]] = g[g.columns[2:]].astype(float).round(1)
    save(g, 'weather_daily')


def t_weather_normal():
    """평년(1991~2020 같은 월·일 앞뒤 3일). 팀 결과의 평년_ 열 그대로 (1991~2014 ASOS 원본이 있어야 채워짐)"""
    w = read_wx()
    if w is None:
        return
    w = w.dropna(subset=['평년_평균기온'])
    if w.empty:
        print('  weather_normal: 평년 값 없음 (weather/README 8번: ASOS 1991~2014 원본 넣기)'); return
    w['month'] = w.날짜.str[5:7].astype(int); w['day'] = w.날짜.str[8:10].astype(int)
    n = w.drop_duplicates(['region_id', 'month', 'day'], keep='last')
    o = pd.DataFrame({'region_id': n.region_id, 'month': n.month, 'day': n.day, 'temp_normal': n.평년_평균기온, 'temp_max_normal': n.평년_최고기온,
                      'temp_min_normal': n.평년_최저기온, 'rain_normal': n.평년_강수량})
    o[o.columns[3:]] = o[o.columns[3:]].astype(float).round(2)
    save(o.sort_values(['region_id', 'month', 'day']), 'weather_normal')


WRN = {'W': '강풍', 'R': '호우', 'C': '한파', 'D': '건조', 'T': '태풍', 'S': '대설', 'Y': '황사', 'H': '폭염', 'F': '안개',
       'O': '해일', 'N': '지진해일', 'V': '풍랑'}
LAND = {'강풍', '호우', '한파', '건조', '태풍', '대설', '황사', '폭염'}
NM = {'경기도': '경기', '서해5도': '인천', '강원도': '강원', '충청남도': '충남', '충청북도': '충북', '전라남도': '전남', '흑산도.홍도': '전남', '전라북도': '전북',
      '전북자치도': '전북', '경상북도': '경북', '울릉도.독도': '경북', '경상남도': '경남', '제주도': '제주', '서울': '서울', '인천': '인천', '대전': '대전',
      '광주': '광주', '대구': '대구', '부산': '부산', '울산': '울산', '세종': '세종'}


def t_warning(since):
    regf = RAW / 'warning' / 'wrn_reg.txt'
    regf = regf if regf.exists() else REF / 'wrn_reg.txt'
    if not regf.exists():
        return
    up, name, ok_now = {}, {}, set()
    for line in regf.read_text(encoding='utf-8').splitlines():
        if line.startswith('#') or ',' not in line:
            continue
        p = [x.strip() for x in line.split(',')]
        if len(p) >= 6:
            up[p[0]] = p[4]; name[p[0]] = p[5]
            if p[2][:4] >= '2026':
                ok_now.add(p[0])

    def sido(r, d=0):
        if r not in up or d > 6:
            return None
        return NM.get(name[r]) if up[r] == 'L1000000' else sido(up[r], d + 1)
    rid = dict(zip(ref('region').name, ref('region').region_id))
    leaf = {r for r in up if r.startswith('L1') and r not in set(up.values())}
    zones = {}
    for r in leaf & ok_now:
        s = sido(r)
        if s:
            zones.setdefault(rid[s], set()).add(r)
    ev = []
    start_m = (since - dt.timedelta(40)).strftime('%Y-%m')  # 그 전에 발표돼 이어지는 특보도 잡기
    for f in sorted(glob.glob(str(RAW / 'warning' / '20*.txt'))):
        if Path(f).stem < start_m:
            continue
        for line in Path(f).read_text(encoding='utf-8').splitlines():
            p = [x.strip() for x in line.split(',')]
            if len(p) < 8 or not p[0].isdigit():
                continue
            ev.append((p[1], p[4], p[5], p[6], p[7]))  # 발효시각 TM_EF, 구역, 종류, 수준, 명령
    if not ev:
        return
    e = pd.DataFrame(ev, columns=['tm', 'reg', 'w', 'lvl', 'cmd']).sort_values('tm')
    e['type'] = e.w.map(WRN)
    e = e[e.type.isin(LAND) & e.reg.isin(leaf)]
    ON, OFF = {'1', '2', '5', '6'}, {'3', '4', '7'}
    rows = []
    end = (C.today() + dt.timedelta(1)).strftime('%Y%m%d2359')
    for (reg, typ), g in e.groupby(['reg', 'type']):
        cur = None
        for r in g.itertuples():
            if r.cmd in ON:
                if cur is None:
                    cur = [r.tm, int(r.lvl) if r.lvl.isdigit() else 0]
                else:
                    cur[1] = max(cur[1], int(r.lvl) if r.lvl.isdigit() else 0)
            elif r.cmd in OFF and cur:
                rows.append((reg, typ, cur[0], r.tm, cur[1])); cur = None
        if cur:
            rows.append((reg, typ, cur[0], end, cur[1]))
    out = []
    for reg, typ, a, b, lv in rows:
        s = sido(reg)
        if not s:
            continue
        for d in pd.date_range(pd.to_datetime(a[:8]), pd.to_datetime(b[:8])):
            if d.date() >= since:
                out.append((d.date().isoformat(), rid[s], typ, reg, lv))
    o = pd.DataFrame(out, columns=['date', 'region_id', 'warn_type', 'reg', 'lvl'])
    lvmap = {2: 1, 3: 2, 4: 3}  # 주의보 1 · 경보 2 · 중대경보 3 (예비특보 1 은 뺌)
    o['level'] = o.lvl.map(lvmap)
    o = o[o.level.notna()]
    g = o.groupby(['date', 'region_id', 'warn_type']).agg(level=('level', 'max'), n=('reg', 'nunique')).reset_index()
    g['area_share'] = (g.n / g.region_id.map(lambda r: max(len(zones.get(r, ())), 1))).clip(upper=1).round(3)
    g['level'] = g.level.astype(int)
    save(g[['date', 'region_id', 'warn_type', 'level', 'area_share']], 'weather_warning_daily')


SKY = {'1': '맑음', '3': '구름많음', '4': '흐림'}
PTY = {'1': '비', '2': '비/눈', '3': '눈', '4': '소나기'}


def latlon_to_grid(lat, lon):
    import math
    RE, GRID, SLAT1, SLAT2, OLON, OLAT, XO, YO = 6371.00877, 5.0, 30.0, 60.0, 126.0, 38.0, 43, 136
    D = math.pi / 180.0
    re_ = RE / GRID; s1, s2, olon, olat = SLAT1 * D, SLAT2 * D, OLON * D, OLAT * D
    sn = math.log(math.cos(s1) / math.cos(s2)) / math.log(math.tan(math.pi * 0.25 + s2 * 0.5) / math.tan(math.pi * 0.25 + s1 * 0.5))
    sf = math.pow(math.tan(math.pi * 0.25 + s1 * 0.5), sn) * math.cos(s1) / sn
    ro = re_ * sf / math.pow(math.tan(math.pi * 0.25 + olat * 0.5), sn)
    ra = re_ * sf / math.pow(math.tan(math.pi * 0.25 + lat * D * 0.5), sn)
    th = lon * D - olon
    th = th - 2 * math.pi if th > math.pi else th + 2 * math.pi if th < -math.pi else th
    th *= sn
    return int(ra * math.sin(th) + XO + 0.5), int(ro - ra * math.cos(th) + YO + 0.5)


def t_now():
    """시·도 오늘 날씨: 팀 예보 수집기 DB(data/weather/raw/fcst/진행상태.sqlite3)의 가장 최근 단기예보.
    시·도 안 시군구 격자들의 값을 모아 기온은 평균, 최저·최고는 평균, 강수확률은 최대, 하늘은 가장 많은 값"""
    import gzip, sqlite3
    db = C.DATA / 'weather' / 'raw' / 'fcst' / '진행상태.sqlite3'
    if not db.exists():
        print(f'  예보 DB 없음: {db} (collect.py fcst 먼저)'); return
    sg = pd.read_csv(C.HERE / 'weather' / 'ref' / '시군구_좌표.csv', encoding='utf-8-sig').dropna(subset=['위도', '경도'])
    sido_of = {}
    for r in sg.itertuples():
        sido_of.setdefault(latlon_to_grid(float(r.위도), float(r.경도)), r.시도)
    con = sqlite3.connect(db)
    issue = con.execute("SELECT max(issue) FROM raw WHERE kind='short'").fetchone()[0]
    if not issue:
        return
    day = C.today().strftime('%Y%m%d')
    recs = []
    for point, body in con.execute("SELECT point, body FROM raw WHERE kind='short' AND issue=?", (issue,)):
        nx, ny = map(int, point.split(','))
        sd = sido_of.get((nx, ny))
        if not sd:
            continue
        for it in json.loads(gzip.decompress(body)):
            if it.get('fcstDate') == day:
                recs.append((sd, it['category'], it['fcstTime'], it['fcstValue']))
    con.close()
    if not recs:
        return
    f = pd.DataFrame(recs, columns=['sido', 'cat', 'tm', 'val'])
    f['num'] = pd.to_numeric(f.val, errors='coerce')
    rid = dict(zip(ref('region').name, ref('region').region_id))
    bt = dt.datetime.strptime(issue, '%Y%m%d%H%M').replace(tzinfo=C.KST)
    rows = []
    for sd, g in f.groupby('sido'):
        t12 = '1200' if (g.tm == '1200').any() else g.tm.min()
        c = lambda cat, tm=None: g[(g.cat == cat) & ((g.tm == tm) if tm else True)]
        tmn = c('TMN').num.mean(); tmx = c('TMX').num.mean()
        if pd.isna(tmn): tmn = c('TMP').num.min()
        if pd.isna(tmx): tmx = c('TMP').num.max()
        pty = c('PTY', t12).val.mode(); sky = c('SKY', t12).val.mode()
        pty = pty.iloc[0] if len(pty) else '0'; sky = sky.iloc[0] if len(sky) else '1'
        pop = c('POP').num.max()
        note = []
        if pd.notna(tmx) and pd.notna(tmn) and tmx - tmn >= 10: note.append('일교차 큼')
        if pd.notna(tmn) and tmn <= 0: note.append('서리·냉해 주의')
        if pd.notna(tmx) and tmx >= 33: note.append('폭염 주의 · 시설 환기')
        if pd.notna(pop) and pop >= 60: note.append('비 예보 · 수확 일정 조정')
        rows.append({'base_time': bt.isoformat(), 'region_id': rid.get(sd), 'temp': c('TMP', t12).num.mean(), 'temp_min': tmn, 'temp_max': tmx,
                     'sky': PTY.get(str(pty)) or SKY.get(str(sky), ''), 'icon': f'pty{pty}' if str(pty) != '0' else f'sky{sky}',
                     'rain_prob': pop, 'humidity': c('REH', t12).num.mean(), 'wind': c('WSD', t12).num.mean(), 'soil_temp': '',
                     'note': ' · '.join(note) or '작물 생육에 무난한 날씨'})
    df = pd.DataFrame(rows).dropna(subset=['region_id']).round(1)
    for col in ('rain_prob', 'humidity'):
        df[col] = df[col].round().astype('Int64')
    save(df, 'weather_region_now')


def t_holiday():
    rows = []
    for f in glob.glob(str(RAW / 'holiday' / '*.json')):
        for x in json.loads(Path(f).read_text(encoding='utf-8')):
            d = str(x.get('locdate', ''))
            if len(d) == 8 and x.get('isHoliday', 'Y') == 'Y':
                rows.append({'date': f'{d[:4]}-{d[4:6]}-{d[6:]}', 'name': x.get('dateName', '')})
    if not rows:
        return
    h = pd.DataFrame(rows).drop_duplicates('date')
    # 도매시장 휴장: 설·추석 연휴는 휴장. 그 밖 공휴일은 시장마다 달라 원장에 거래가 없던 날로 판단
    h['is_market_closed'] = h.name.str.contains('설날|추석')
    f = HIST / 'price_all.csv'
    if f.exists():
        p = pd.read_csv(f, usecols=['date', 'market_code'], dtype=str)
        traded = set(p[p.market_code == 'national'].date)
        past = h.date < C.today().isoformat()
        h.loc[past, 'is_market_closed'] = ~h.loc[past, 'date'].isin(traded)
    save(h.sort_values('date'), 'holiday')


# ───────────── 산지공판장 · 가락 반입 · aT 출하예약 · 환율 · 정책 (예측 입력·화면 보조) ─────────────
def t_producer(since):
    """산지공판장 일별: 날짜 × 공판장 × 품목 물량·금액·단가 (+ 전국 'national')"""
    files = sorted(f for f in glob.glob(str(RAW / 'sanji' / '*.csv.gz')) if Path(f).name[:8] >= since.strftime('%Y%m%d'))
    if not files:
        return
    a = pd.concat([pd.read_csv(f, dtype=str, compression='gzip') for f in files])
    a['date'] = pd.to_datetime(a.정산일자.str[:8], format='%Y%m%d').dt.date.astype(str)
    a['code4'] = a.대분류코드.str.zfill(2) + a.중분류코드.str.zfill(2)
    it = ref('item')
    a['item_code'] = a.code4.map(dict(zip(it.code4, it.item_code)))
    for c in ('총물량', '총금액'):
        a[c] = pd.to_numeric(a[c], errors='coerce')
    a = a[a.item_code.notna() & (a.총물량 > 0) & (a.총금액 > 0)]
    a['market'] = a.법인_공판장코드.str.strip(); a['market_name'] = a.법인_공판장명.str.strip()
    nat = a.assign(market='national', market_name='전국')
    g = pd.concat([a, nat]).groupby(['date', 'market', 'market_name', 'item_code'], as_index=False).agg(volume_kg=('총물량', 'sum'), amount_won=('총금액', 'sum'))
    g['price'] = (g.amount_won / g.volume_kg).round().astype('Int64')
    save(g.rename(columns={'market': 'producer_code', 'market_name': 'producer_name'}), 'producer_price_daily')


def t_garak_inout(since):
    """가락 경매전(그날 경매 전 집계)·경매후(그날 실제 반입) 품목 반입량. 단위 톤 → kg. 소계·합계 줄은 뺌"""
    gi = ref('garak_item') if (REF / 'garak_item.csv').exists() else None
    out = []
    for svc, kind, name_col, code_col, tot in (('GarakAuctionBefore', 'before', 'GUBUN', None, 'TOT'), ('GarakAuctionAfter', 'after', 'ITM_NM', 'ITM_CD', 'SUM_TOT')):
        f = RAW / 'garak_inout' / f'{svc}.csv'
        if not f.exists():
            continue
        x = pd.read_csv(f, dtype=str)
        x['date'] = pd.to_datetime(x.TODATE.str[:8], format='%Y%m%d', errors='coerce').dt.date.astype(str)
        x = x[x.date >= str(since)]
        nm = x[name_col].fillna('').str.strip()
        bad = nm.str.contains(r'계$|합계|소계') | x.BURYU.fillna('').str.contains('계')
        if code_col:
            bad |= x[code_col].fillna('').str.strip() == ''
        x = x[~bad]
        y = pd.DataFrame({'date': x.date, 'kind': kind, 'garak_name': nm[~bad], 'garak_code': x[code_col].str.strip() if code_col else '-',
                          'volume_kg': (pd.to_numeric(x[tot], errors='coerce') * 1000).round(1)})
        if gi is not None:
            key = 'before_name' if kind == 'before' else 'after_code'
            src = y.garak_name if kind == 'before' else y.garak_code
            y['item_code'] = src.map(dict(zip(gi[key], gi.item_code))).fillna('-').replace('', '-')
        else:
            y['item_code'] = '-'
        out.append(y)
    if out:
        g = pd.concat(out)
        g = g.groupby(['date', 'kind', 'garak_name', 'garak_code', 'item_code'], as_index=False).volume_kg.sum()
        save(g, 'garak_inout_daily')


def _kg(q, u, nm):
    nm = str(nm).strip().lower()
    f = {'kg': 1, '키로그램': 1, '킬로그램': 1, 'g': 0.001, '그램': 0.001, '톤': 1000, 't': 1000, 'ton': 1000}.get(nm)
    return q * u * f if f else np.nan


def t_at_resv(since):
    """aT 전국 도매시장 출하예약(전자송품장): 출하예정일 × 시장 × 품목 × 품종(소분류) 예약물량 kg. 수집시각이 늦은 파일이 최종"""
    files = sorted(f for f in glob.glob(str(RAW / 'at_resv' / '*.csv')) if Path(f).stem >= str(since))
    if not files:
        return
    x = pd.concat([pd.read_csv(f, dtype=str) for f in files if Path(f).stat().st_size > 100] or [pd.DataFrame()])
    if x.empty:
        return
    x['code4'] = x.gds_lclsf_cd.str.zfill(2) + x.gds_mclsf_cd.str.zfill(2)
    it = ref('item')
    x['item_code'] = x.code4.map(dict(zip(it.code4, it.item_code)))
    x = x[x.item_code.notna()]
    x['kg'] = [_kg(float(q or 0), float(u or 0), n) for q, u, n in zip(x.spmt_qty.fillna(0), x.unit_qty.fillna(0), x.unit_nm)]
    g = x.groupby(['spmt_dt', 'whsl_mrkt_cd', 'item_code', 'gds_sclsf_cd'], as_index=False).agg(
        reserved_kg=('kg', 'sum'), invoice_rows=('kg', 'size'), collected_at=('수집시각', 'max'))
    g = g.rename(columns={'spmt_dt': 'date', 'whsl_mrkt_cd': 'market_code', 'gds_sclsf_cd': 'variety_code'})
    g['date'] = g.date.str[:10]   # API 값이 '2026-10-25T00:00:00Z' 모양
    g['reserved_kg'] = g.reserved_kg.round(1)
    save(g, 'shipment_reservation_daily')


def t_fx(since):
    f = RAW / 'fx' / 'fx_daily.csv'
    if not f.exists():
        return
    x = pd.read_csv(f, dtype=str)
    x = x[x.date >= str(since)]
    x['value'] = pd.to_numeric(x.value.str.replace(',', ''), errors='coerce')
    x = x.drop_duplicates(['date', 'item_code'], keep='last')
    save(x.rename(columns={'item_code': 'currency_code', 'item_name': 'currency_name', 'value': 'rate'})[['date', 'currency_code', 'currency_name', 'rate']], 'fx_daily')


def t_policy(since):
    """정부 수급정책 문서 목록: 공지 후보·예측 입력(정부 개입 시점). 게시일 없으면 수집일"""
    f = C.DATA / 'policy' / '01_전체문서_수집목록.csv'
    if not f.exists():
        return
    x = pd.read_csv(f, dtype=str, encoding='utf-8-sig')
    x['date'] = x.게시일.fillna('').str[:10]
    x.loc[x.date == '', 'date'] = x.발표일시.fillna('').str[:10]          # 게시일·발표일시 둘 다 없으면 비워 둠(수집일로 채우지 않음)
    x['collected_at'] = x.수집일시.fillna('')
    x = x[(x.date >= str(since)) | ((x.date == '') & (x.collected_at.str[:10] >= str(since)))]
    save(pd.DataFrame({'doc_id': x.문서ID, 'date': x.date, 'source': x.출처, 'title': x.제목, 'url': x.원문주소, 'status': x.본문상태,
                       'collected_at': x.collected_at}), 'policy_doc')


def t_log():
    f = C.LOG / 'collect_log.csv'
    if f.exists():
        save(pd.read_csv(f), 'collect_log')


STEPS = ['refs', 'price_daily', 'price_index_daily', 'market_factor', 'piece_weight', 'retail_price_daily', 'weather_daily', 'weather_normal',
         'weather_warning_daily', 'weather_region_now', 'holiday', 'producer_price_daily', 'garak_inout_daily',
         'shipment_reservation_daily', 'fx_daily', 'policy_doc', 'collect_log']


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--since', help='YYYY-MM-DD (기본: 14일 전)')
    ap.add_argument('--only', nargs='*', choices=STEPS)
    a = ap.parse_args()
    since = dt.date.fromisoformat(a.since) if a.since else C.today() - dt.timedelta(14)
    todo = a.only or STEPS
    print(f'표 만들기: {since} 부터 → {OUT}', flush=True)
    for s in todo:
        {'refs': t_refs, 'price_daily': lambda: t_prices(since), 'price_index_daily': lambda: t_index(since),
         'market_factor': t_market_factor, 'piece_weight': lambda: t_piece_weight(since), 'retail_price_daily': lambda: t_retail(since), 'weather_daily': lambda: t_weather(since),
         'weather_normal': t_weather_normal, 'weather_warning_daily': lambda: t_warning(since), 'weather_region_now': t_now,
         'holiday': t_holiday, 'producer_price_daily': lambda: t_producer(since), 'garak_inout_daily': lambda: t_garak_inout(since),
         'shipment_reservation_daily': lambda: t_at_resv(since), 'fx_daily': lambda: t_fx(since), 'policy_doc': lambda: t_policy(since),
         'collect_log': t_log}[s]()


if __name__ == '__main__':
    main()

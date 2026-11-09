# -*- coding: utf-8 -*-
"""data/tables/*.csv → PostgreSQL (같은 키면 덮어쓰기 = upsert). 2026-11-06
  pip install psycopg2-binary
  python load_db.py --init        # schema.sql 실행 (처음 한 번)
  python load_db.py               # data/tables 에 있는 표를 전부 넣기
접속 정보: .env 의 PGHOST PGPORT PGDATABASE PGUSER PGPASSWORD (없으면 localhost:5432/farmdb, postgres)
"""
import argparse
import csv
import os
import sys

import common as C

# 표 이름: 기본키 (넣는 순서 = FK 순서)
TABLES = [
    ('region', ['region_id']), ('market', ['market_code']), ('index_group', ['group_code']), ('item', ['item_code']),
    ('variety_unit', ['unit_id']), ('grade_map', ['source', 'raw_grade']), ('holiday', ['date']),
    ('price_daily', ['date', 'market_code', 'item_code', 'grade']),
    ('price_origin_daily', ['date', 'market_code', 'item_code', 'origin_region_id', 'is_import']),
    ('price_unit_daily', ['date', 'unit_id']), ('retail_price_daily', ['date', 'item_code']),
    ('price_index_daily', ['date', 'group_code']), ('market_factor', ['item_code', 'market_code', 'month']),
    ('weather_daily', ['date', 'region_id']), ('weather_normal', ['region_id', 'month', 'day']),
    ('weather_region_now', ['base_time', 'region_id']), ('weather_warning_daily', ['date', 'region_id', 'warn_type']),
    ('producer_price_daily', ['date', 'producer_code', 'item_code']),
    ('garak_inout_daily', ['date', 'kind', 'garak_name', 'garak_code', 'item_code']),
    ('shipment_reservation_daily', ['date', 'market_code', 'item_code', 'variety_code']),
    ('fx_daily', ['date', 'currency_code']), ('policy_doc', ['doc_id']),
    ('collect_log', ['source', 'started_at']),
]


def connect():
    C.load_env()
    try:
        import psycopg2
    except ImportError:
        sys.exit('psycopg2 가 없습니다: pip install psycopg2-binary')
    return psycopg2.connect(host=os.getenv('PGHOST', 'localhost'), port=os.getenv('PGPORT', '5432'),
                            dbname=os.getenv('PGDATABASE', 'farmdb'), user=os.getenv('PGUSER', 'postgres'),
                            password=os.getenv('PGPASSWORD', ''))


def load(cur, name, keys):
    f = C.OUT / f'{name}.csv'
    if not f.exists():
        return 0
    with f.open(encoding='utf-8') as fh:
        cols = next(csv.reader(fh))
    q = lambda c: '"' + c + '"'
    cur.execute(f'CREATE TEMP TABLE _t (LIKE {name} INCLUDING DEFAULTS) ON COMMIT DROP')
    if name == 'collect_log':
        cur.execute('ALTER TABLE _t ALTER COLUMN log_id DROP NOT NULL')
    with f.open(encoding='utf-8') as fh:
        cur.copy_expert(f"COPY _t ({','.join(map(q, cols))}) FROM STDIN WITH (FORMAT csv, HEADER true, NULL '')", fh)
    upd = [c for c in cols if c not in keys]
    set_ = ', '.join(f'{q(c)} = EXCLUDED.{q(c)}' for c in upd) or None
    k = ','.join(map(q, keys))   # 같은 키가 파일에 두 번 있으면 마지막 줄만 (ctid 순서)
    cur.execute(f"INSERT INTO {name} ({','.join(map(q, cols))}) SELECT DISTINCT ON ({k}) {','.join(map(q, cols))} FROM _t ORDER BY {k}, ctid DESC "
                f"ON CONFLICT ({k}) DO " + (f'UPDATE SET {set_}' if set_ else 'NOTHING'))
    n = cur.rowcount
    cur.execute('DROP TABLE _t')
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--init', action='store_true'); ap.add_argument('--only', nargs='*')
    a = ap.parse_args()
    con = connect()
    t0 = C.now()
    try:
        with con:
            with con.cursor() as cur:
                if a.init:
                    cur.execute((C.HERE / 'schema.sql').read_text(encoding='utf-8'))
                    print('schema.sql 실행')
                tot = 0
                for name, keys in TABLES:
                    if a.only and name not in a.only:
                        continue
                    n = load(cur, name, keys)
                    if n:
                        print(f'  {name}: {n:,}행 넣음/고침'); tot += n
        C.write_log('db_load', t0, True, rows_saved=tot)
    except Exception as e:
        C.write_log('db_load', t0, False, error=str(e)); raise
    finally:
        con.close()


if __name__ == '__main__':
    main()

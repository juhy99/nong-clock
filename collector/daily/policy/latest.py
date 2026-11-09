# -*- coding: utf-8 -*-
"""NongClock 정부정책 수집기(collector.py)로 목록 앞쪽 몇 쪽만 다시 보고 새 문서와 그 첨부만 받는다. (팜비드 묶음용, 2026-11-06)
  python latest.py <쪽수=3> <결과 폴더=../data/policy>
원래 수집기를 통째로 돌리면 예전 첨부 오류를 매번 다시 시도해 오래 걸림. 처음 전체는 python collector.py --mode run (config 의 output_dir 을 결과 폴더로)
"""
import importlib.util, json, pathlib, sys
from pathlib import Path

# 첨부 글자에 짝 없는 서로게이트가 있으면 export가 UnicodeEncodeError로 멈춤 → '?'로 바꿔 저장
_wt = pathlib.Path.write_text
pathlib.Path.write_text = lambda self, data, encoding=None, errors=None, newline=None: _wt(self, data, encoding=encoding, errors=errors or 'replace', newline=newline)

d = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('collector', d / 'collector.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
cfg = json.loads((d / 'config.json').read_text(encoding='utf-8-sig'))
cfg['max_pages'] = int(sys.argv[1]) if len(sys.argv) > 1 else 3
out = Path(sys.argv[2]) if len(sys.argv) > 2 else d.parent / 'data' / 'policy'
out.mkdir(parents=True, exist_ok=True)
c = m.Collector(cfg, out)
try:
    for s in cfg['sources']:
        try:
            c.scan(s, False, True)
        except Exception as e:
            print('목록 실패:', s['id'], str(e)[:200], flush=True)
    c.commit()
    new = list(c.db.execute("select url,source,title,pub from docs where status='queued'"))
    print('새 문서', len(new), '건', flush=True)
    for r in new:
        try:
            c.detail(*r)
        except Exception as e:
            print('본문 실패:', r[0], str(e)[:200], flush=True)
    c.commit()
    urls = {r[0] for r in new}
    for u, doc in list(c.db.execute("select url,doc from files where status='queued'")):
        if doc in urls:
            try:
                c.attachment(u, doc)
            except Exception as e:
                print('첨부 실패:', u, str(e)[:200], flush=True)
    c.commit()
finally:
    c.export()
    c.db.close()

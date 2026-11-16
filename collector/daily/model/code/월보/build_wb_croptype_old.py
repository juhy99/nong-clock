r"""농업관측월보 옛 호(문장형) → 작형별 지표 전년비 (2026-10-27)
페이지 텍스트의 줄바꿈을 없애고, '<작형+품목> ... <지표>(은|는|이|가)? ... (작년|전년)(보다|대비) N% (증가|감소)' 를 찾는다.
작형 이름이 지표 앞 40자 안에 있어야 하고, 지표와 증감률 사이는 60자 안. 평년 대비만 있는 문장은 버림.
사용: python build_wb_croptype_old.py <텍스트폴더> <출력폴더>
"""
import os, re, sys
import pandas as pd, numpy as np
SRC, OUT = sys.argv[1], sys.argv[2]
ITEMS = {'엽근채소': ['배추', '무', '당근', '양배추'], '양념채소': ['양파', '마늘', '대파', '건고추'], '감자': ['감자']}
SEAS = [('준고랭지', '고랭지'), ('고랭지', '고랭지'), ('여름', '고랭지'), ('월동', '겨울'), ('겨울', '겨울'), ('가을', '가을'), ('시설봄', '봄(시설)'), ('하우스봄', '봄(시설)'), ('노지봄', '봄'), ('봄', '봄'),
        ('조생', '조생'), ('중만생', '중만생'), ('난지', '난지'), ('한지', '한지')]
IND = {'재배의향면적': 'area', '재배 의향면적': 'area', '의향면적': 'area', '정식의향면적': 'area', '파종의향면적': 'area', '재배면적': 'area', '단수': 'yld', '생산량': 'prod', '출하량': 'prod', '저장량': 'store', '재고량': 'store'}
rows = []
pat_ind = re.compile('|'.join(sorted(map(re.escape, IND), key=len, reverse=True)))
for bun, items in ITEMS.items():
    if not os.path.exists(os.path.join(SRC, f'{bun}_페이지텍스트.csv')): continue   # (자동 실행용) 그 분야 새 호가 없으면 건너뜀
    d = pd.read_csv(os.path.join(SRC, f'{bun}_페이지텍스트.csv'))
    for r in d.itertuples():
        t = re.sub(r'\s+', ' ', str(r.텍스트))
        for m in pat_ind.finditer(t):
            before = t[max(0, m.start() - 40):m.start()].replace(' ', '')
            item = None
            for it in sorted(items, key=len, reverse=True):
                if it in before[-25:]: item = it; break
            if not item: continue
            pre = before[:before.rfind(item)] if item in before else ''
            seas = next((v for k, v in SEAS if k in pre[-8:]), '전체')
            after = t[m.end():m.end() + 70]
            cut = re.search(r'(다\.|임\.|음\.|듯|\. |[●•■□◆ㅁ※])', after)
            if cut: after = after[:cut.start() + 1]
            if re.match(r'.{0,30}(작년|전년)[^%]{0,15}(과|와)?\s*비슷', after) and not re.search(r'\d\s*%', after[:40]):
                rows.append(dict(분야=bun, 연도=int(r.연도), 발행월=int(r.발행월), 파일=r.파일, 품목=item, 작형=seas, 지표=IND[m.group(0)], 전년비_pct=0.0, 원문=t[max(0, m.start() - 40):m.end() + 70]))
                continue
            mm = re.search(r'(작년|전년|금년보다 작년)[^%]{0,25}?(\d+(?:\.\d+)?)\s*%\s*(증가|감소|늘|줄|많|적)', after)
            if not mm: continue
            seg = after[:mm.start()]
            if '평년' in seg and '작년' not in seg and '전년' not in seg: continue
            v = float(mm.group(2)) * (1 if mm.group(3) in ('증가', '늘', '많') else -1)
            if abs(v) > 200: continue
            rows.append(dict(분야=bun, 연도=int(r.연도), 발행월=int(r.발행월), 파일=r.파일, 품목=item, 작형=seas, 지표=IND[m.group(0)], 전년비_pct=v,
                             원문=t[max(0, m.start() - 40):m.end() + 70]))
X = pd.DataFrame(rows, columns=['분야', '연도', '발행월', '파일', '품목', '작형', '지표', '전년비_pct', '원문']); X['발행'] = X.연도.astype(str) + '-' + X.발행월.astype(str).str.zfill(2)
os.makedirs(OUT, exist_ok=True)
X.to_csv(os.path.join(OUT, '03_옛호_문장형_작형지표_long.csv'), index=False, encoding='utf-8-sig')
W = X.groupby(['품목', '작형', '지표', '발행']).전년비_pct.median().reset_index()
W.to_csv(os.path.join(OUT, '04_옛호_품목_작형_지표_발행월_전년비.csv'), index=False, encoding='utf-8-sig')
print(len(X), X.groupby('연도').size().to_dict())
print(W.groupby(['품목', '지표']).size().unstack(fill_value=0))

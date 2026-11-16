# -*- coding: utf-8 -*-
# 70 w11a — 관측월보 과일 페이지텍스트(D:\claude\02_전처리\04\참고_페이지텍스트\과일_페이지텍스트.csv)에서 사과·배·단감·감귤·포도 생산량 전망(전년비 %)과 착과수·꽃수 신호를 다시 뽑음 (2026-11-02)
# 방식: A 문장 / A2 긴 문장(…% 적은 N만 톤) / A3 각각 / A4 머리말(생산량: … (전년 대비 a~b%)) / B 과일 생산량 요약표 / C 품목 표(재배면적·단수·생산량 전년 대비 세 번째 값) / D 착과수·꽃수
# 실행: python w11a_월보_생산전망_재추출.py <과일_페이지텍스트.csv> <출력.csv>
import re, sys, pandas as pd, numpy as np
SRC, OUT = sys.argv[1], sys.argv[2]
d = pd.read_csv(SRC)
def norm(s):
    s = re.sub(r'\s+', ' ', str(s))
    for a in '∼～〜': s = s.replace(a, '~')
    for a in '–−—': s = s.replace(a, '-')
    return s
d['t'] = d.텍스트.map(norm)
NUM = r'[-+]?\d{1,2}(?:\.\d+)?'
PCT = rf'(?P<a>{NUM})(?:\s*~\s*(?P<b>{NUM}))?\s*%'
YR = r'(?:전년|지난해|작년)\s*(?:대비|보다|에\s*비해|에\s*비하여)?'
UP, DN = ('증가', '많', '늘', '증대', '상회'), ('감소', '적', '줄', '하회', '감축')
ITEM = {'사과': r'(?<![가-힣])사과', '배': r'(?<![가-힣])배', '단감': r'단감', '포도': r'(?<![가-힣])포도',
        '감귤': r'(?:감귤\s*\(\s*노지온주\s*\)|노지\s*온주|노지\s*감귤|(?<![가-힣])감귤)'}
BAD_MID = ('물량', '출하', '저장', '수입', '하우스', '시설', '품종', '월별', '착과', '꽃', '가공', '수출', '조생', '중생', '만생', '극조생', '세계', '미국', '칠레', '중국', '페루', '뉴질랜드', '호주', '일본', '각각', '노지포도', '·', ',', '와 ', '과 ')
VAR = ('후지', '홍로', '쓰가루', '아오리', '부사', '신고', '원황', '화산', '부유', '서촌', '캠벨', '거봉', '샤인', '머스캣', '머스켓', 'MBA', '델라웨어', '한라봉', '천혜향', '레드향', '만감', '감홍', '시나노', '썸머킹', '태추', '차랑')
BAD_GAP = ('공급', '증감률', '지역', '배 ', '포도', '사과', '단감', '감귤', '온주', '복숭아', '반입', '단수', '면적', '착과', '출하', '가격', '꽃', '수입', '전월', '저장', '각각', '수출', '성목', '시설', '노지포도', '하우스')
def sgn(a, b, tail):
    a = float(a); v = a if b is None else (a + float(b)) / 2
    w = re.match(r'\s*\)?\s*(?:정도|내외|수준|가량|씩)?\s*(증가|많|늘|증대|상회|감소|적|줄|하회|감축)?', tail).group(1)
    if w in DN and v > 0: v = -v
    if w is None and b is None and a >= 0 and not re.match(r'\s*\)', tail):
        return None          # 방향 단어도 부호도 없으면 버림
    if w is None and re.match(r'\s*\)', tail) and a > 0 and b is None:
        # '(전년 대비 16.2%)' 처럼 괄호만: 앞 문장 방향은 모름 → 버림
        return None
    if re.search(r'(저장|출하|반입|년산)', tail[:30]) or re.match(r'\s*\)?\s*\S{0,3}?하였', tail): return None
    return v
rows = []
def add(r, it, kind, v, src, txt):
    rows.append({'연도': int(r.연도), '발행월': int(r.발행월), '파일': r.파일, '페이지': r.페이지, '품목': it, '지표': kind, '전년비_pct': round(v, 2), '방식': src, '원문': txt[:220]})
for r in d.itertuples():
    t = r.t
    # A. 문장: <품목> ... 생산량 ... 전년 대비 x% 증가/감소 | 전년과 비슷
    for it, ip in ITEM.items():
        for m in re.finditer(ip + r'(?P<mid>[^.%()]{0,28}?)생산량(?P<tail>.{0,130})', t):
            mid = m.group('mid')
            if any(k in mid for k in BAD_MID) or any(v in mid for v in VAR) or re.search(r'\d{3,}', mid): continue
            if it != '감귤' and re.search(r'(노지온주|감귤|복숭아|자두|키위|매실|참다래|유자)', mid): continue
            tail = m.group('tail'); y = re.search(YR, tail)
            if not y: continue
            gap = tail[:y.start()]
            if re.search(r'[^가-힣]배[^가-힣]', ' '+gap+' ') or any(k in gap for k in BAD_GAP) or len(gap) > 70: continue
            after = tail[y.end():y.end() + 45]
            if re.match(r'\s*(과|와)\s*(비슷|같|유사)', after) or re.match(r'\s*수준', after):
                add(r, it, '생산량', 0.0, 'A문장', t[m.start():m.start() + 200]); continue
            p = re.search(PCT, after)
            if not p or any(k in after[:p.start()] for k in BAD_GAP) or p.start() > 25: continue
            v = sgn(p.group('a'), p.group('b'), after[p.end():])
            if v is None or abs(v) > 60: continue
            add(r, it, '생산량', v, 'A문장', t[m.start():m.start() + 200])
    # B. 요약표: 과일 생산량 (전년대비) 증감률/전망 [단위:%] [구분] <품목들> [전년대비] <숫자들>
    NM = r'(?:사과|배|감귤\s*\(\s*착과수\s*\)|노지온주\s*\(\s*착과수\s*\)|감귤\s*\([^)]{0,8}\)|노지온주|노지감귤|감귤|노지포도|포도|복숭아(?:\s*\([^)]{0,8}\))?|단감|자두|키위)'
    NV = r'[-+]?\d{1,2}(?:\.\d+)?(?:\s*~\s*[-+]?\d{1,2}(?:\.\d+)?)?'
    for m in re.finditer(r'과일\s*생산량[^가-힣]{0,3}(?:및\s*착과수\s*)?(?:전년\s*대비\s*|작년\s*대비\s*)?(?:증감률|전망)', t):
        seg = t[m.end():m.end() + 300] + ' '
        g = re.match(r'\s*(?:전망\s*)?(?:작년\s*대비\s*|전년\s*대비\s*)?(?:단위\s*:?\s*%\s*)?(?:생산량\s*)?(?:구분\s*)?(?:단위\s*:?\s*%\s*)?(?P<names>(?:' + NM + r'\s+){2,8})(?:단위\s*:?\s*%\s*)?(?:작년\s*대비|전년\s*대비)?\s*(?P<nums>(?:' + NV + r'\s+){2,8})', seg)
        if not g: continue
        names = re.findall(NM, g.group('names'))
        nums = re.findall(r'([-+]?\d{1,2}(?:\.\d+)?)(?:\s*~\s*([-+]?\d{1,2}(?:\.\d+)?))?', g.group('nums'))
        if len(nums) < len(names): continue
        for nm, (a, b) in zip(names, nums):
            it = '감귤' if ('감귤' in nm or '온주' in nm) else ('포도' if '포도' in nm else nm)
            if it not in ITEM: continue
            v = float(a) if not b else (float(a) + float(b)) / 2
            if '착과' in nm:
                add(r, it, '착과·꽃', v, 'B요약표', t[m.start():m.end() + 200]); continue
            if abs(v) <= 60: add(r, it, '생산량', v, 'B요약표', t[m.start():m.end() + 200])
    # A2. 긴 문장: <품목> 생산량은 ...(면적·단수 설명)... 전년보다 x% 적은/많은/감소한/증가한 N만 (천)톤
    for it, ip in ITEM.items():
        for m in re.finditer(ip + r'(?P<mid>[^.%()]{0,10}?)생산량(?:은|이)?(?P<tail>.{0,170}?)' + YR + r'\s*(?P<a>\d{1,2}(?:\.\d+)?)\s*%\s*(?P<w>적은|많은|감소한|증가한|늘어난|줄어든|증가된|감소된)\s*(?:\d+\s*만|\d{2,3}\s*천\s*톤|\d+\s*천\s*톤)', t):
            mid, tail = m.group('mid'), m.group('tail')
            if any(k in mid for k in BAD_MID) or any(v in mid for v in VAR): continue
            if re.search(r'(출하량|공급량|반입량|저장량|수입량|각각)', tail) or re.search(r'(?<![가-힣])(사과|배|포도|단감|감귤|노지온주|복숭아)\s*(생산량|는|은)', tail): continue
            v = float(m.group('a')) * (-1 if m.group('w') in ('적은', '감소한', '줄어든', '감소된') else 1)
            if abs(v) <= 60: add(r, it, '생산량', v, 'A2긴문장', t[m.start():m.start() + 220])
    # A3. 각각: 사과·배 생산량은 ... 각각 8%, 22% 증가
    for m in re.finditer(r'(?P<names>(?:(?:사과|배|포도|단감|감귤|노지온주|복숭아|노지포도)\s*[·ㆍ,와과]\s*){1,4}(?:사과|배|포도|단감|감귤|노지온주|복숭아|노지포도))\s*(?:의\s*)?생산량[은이]?(?P<tail>[^.]{0,60}?)' + YR + r'\s*각각\s*(?P<nums>(?:\d{1,2}(?:\.\d+)?\s*%\s*,?\s*){2,5})(?P<w>증가|감소|많|적|늘|줄)', t):
        if re.search(r'(출하|공급|반입|저장|수입|면적|단수)', m.group('tail')): continue
        names = re.findall(r'사과|배|포도|단감|감귤|노지온주|복숭아|노지포도', m.group('names'))
        nums = re.findall(r'(\d{1,2}(?:\.\d+)?)\s*%', m.group('nums'))
        if len(nums) != len(names): continue
        sg = -1 if m.group('w') in ('감소', '적', '줄') else 1
        for nm, a in zip(names, nums):
            it = '감귤' if '온주' in nm else ('포도' if '포도' in nm else nm)
            if it in ITEM: add(r, it, '생산량', sg * float(a), 'A3각각', t[m.start():m.start() + 200])
    # A4. 머리말 + '생산량: N톤 (전년 대비 a~b% 증가)' (2017~ 형식)
    for it, ip in ITEM.items():
        for m in re.finditer(r'(?:\d{4}\s*년\s*)?' + ip + r'\s*생산량\s*(?:은\s*)?(?:전년|평년)[^.]{0,40}?(?:증가|감소|비슷|수준)(?P<seg>.{0,140})', t):
            seg = m.group('seg')
            g = re.search(r'생산량\s*:\s*(?P<pre>[^()]{0,45})\(\s*전년\s*대비\s*(?P<a>[-+]?\d{1,2}(?:\.\d+)?)(?:\s*~\s*(?P<b>[-+]?\d{1,2}(?:\.\d+)?))?\s*%\s*(?P<w>증가|감소)?\s*\)', seg)
            if not g or re.search(r'(출하|저장|하우스|시설)', seg[:g.start()] + g.group('pre')): continue
            a_, b_ = float(g.group('a')), g.group('b'); v = a_ if b_ is None else (a_ + float(b_)) / 2
            if g.group('w') == '감소' and v > 0: v = -v
            if g.group('w') is None and b_ is None and a_ > 0: continue
            if abs(v) <= 60: add(r, it, '생산량', v, 'A4머리말', t[m.start():m.start() + 220])
    # C. 품목 표: <품목> 생산량 전망/추정 ... 구분 재배면적 단수 생산량 ... 전년 대비 a b c → c
    for it, ip in ITEM.items():
        for m in re.finditer(ip + r'\s*생산량\s*(?:전망|추정)(?P<seg>.{0,330})', t):
            seg = m.group('seg')
            if '재배면적' not in seg or '단수' not in seg: continue
            g = re.search(r'전년\s*대비\s*(?:증감률\s*)?(?:\(%\)\s*)?(?P<x>(?:[-+]?\d{1,2}(?:\.\d+)?(?:\s*~\s*[-+]?\d{1,2}(?:\.\d+)?)?\s+){3})', seg + ' ')
            if not g: continue
            nums = re.findall(r'([-+]?\d{1,2}(?:\.\d+)?)(?:\s*~\s*([-+]?\d{1,2}(?:\.\d+)?))?', g.group('x'))
            if len(nums) < 3: continue
            a, b = nums[2]; v = float(a) if not b else (float(a) + float(b)) / 2
            if abs(v) <= 60: add(r, it, '생산량', v, 'C품목표', t[m.start():m.start() + 220])
    # D. 시즌 전 신호: 착과수·꽃수·착과량·개화량
    for it, ip in ITEM.items():
        for m in re.finditer(ip + r'(?P<mid>[^.%()]{0,14}?)(?P<k>착과수|착과량|꽃수|개화량|착화량|결실량)(?P<tail>.{0,80})', t):
            mid = m.group('mid')
            if any(v in mid for v in VAR) or any(k in mid for k in ('하우스', '시설', '수입', '·', ',')): continue
            tail = m.group('tail'); y = re.search(YR, tail)
            if not y or len(tail[:y.start()]) > 30 or any(k in tail[:y.start()] for k in ('생산량', '단수', '면적')): continue
            after = tail[y.end():y.end() + 35]
            if re.match(r'\s*(과|와)\s*(비슷|같|유사)', after): add(r, it, '착과·꽃', 0.0, 'D신호', t[m.start():m.start() + 160]); continue
            p = re.search(PCT, after)
            if not p: continue
            v = sgn(p.group('a'), p.group('b'), after[p.end():])
            if v is None or abs(v) > 80: continue
            add(r, it, '착과·꽃', v, 'D신호', t[m.start():m.start() + 160])
X = pd.DataFrame(rows, columns=['연도', '발행월', '파일', '페이지', '품목', '지표', '전년비_pct', '방식', '원문']).drop_duplicates(['연도', '발행월', '품목', '지표', '전년비_pct', '방식', '원문'])
X.to_csv(OUT, index=False, encoding='utf-8-sig')
print(len(X))

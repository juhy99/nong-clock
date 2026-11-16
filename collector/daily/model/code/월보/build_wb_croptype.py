r"""농업관측월보 페이지 텍스트 → 작형별 수급 지표(재배면적·의향면적·단수·생산량·출하량·저장량·재고량) 숫자 추출 (2026-10-26)
입력: 02_전처리/04_농업관측월보_수치추출/참고_페이지텍스트/{엽근채소,양념채소,감자}_페이지텍스트.csv
방식: 페이지를 줄 단위로 읽으며 '작형 제목'(예: 노지봄배추, 고랭지무, 월동무, 겨울당근)을 기억하고,
      그 아래 '• 지표: 값 단위 (전년 [및 평년] 대비 [각각] a%, b% 증가/감소)' 줄을 읽어 작형에 붙인다.
      제목에 품목만 있고 작형이 없으면 작형='전체'. 숫자 '3만 7천 톤' 같은 한글 단위는 풀어서 톤으로.
사용: python build_wb_croptype.py <텍스트폴더> <출력폴더>
"""
import os, re, sys
import pandas as pd, numpy as np
SRC, OUT = sys.argv[1], sys.argv[2]
ITEMS = {'엽근채소': ['배추', '무', '당근', '양배추'], '양념채소': ['양파', '마늘', '대파', '쪽파', '건고추', '고추'], '감자': ['감자']}
SEASON = [('고랭지', '고랭지'), ('준고랭지', '고랭지'), ('여름', '고랭지'), ('월동', '겨울'), ('겨울', '겨울'), ('가을', '가을'), ('봄', '봄'),
          ('조생', '조생'), ('중만생', '중만생'), ('난지', '난지'), ('한지', '한지'), ('시설', '시설'), ('하우스', '시설'), ('노지', '노지')]
IND = ['재배(의향)면적', '재배의향면적', '정식(의향)면적', '파종(의향)면적', '재배면적', '단수', '생산량', '출하량', '저장량', '재고량', '입고량', '수입량']
NUM = r'([0-9][0-9,\.]*\s*(?:만|천)?\s*[0-9,\.]*\s*(?:천|백)?)\s*(톤|ha|kg/10a|천 톤|만 톤)'
def kor_num(s, unit):
    s = s.replace(',', '').replace(' ', '')
    v = 0.0
    m = re.fullmatch(r'(?:(\d+(?:\.\d+)?)만)?(?:(\d+(?:\.\d+)?)천)?(?:(\d+(?:\.\d+)?)백)?(\d+(?:\.\d+)?)?', s)
    if not m: return np.nan
    a, b, c, d = [float(x) if x else 0 for x in m.groups()]
    v = a * 10000 + b * 1000 + c * 100 + d
    return v
def pct_pair(rest):
    seg = rest[:120]
    if '대비' not in seg: return (np.nan, np.nan)
    nums = [float(x) for x in re.findall(r'(\d+(?:\.\d+)?)\s*%', seg)]
    sign = 0
    if re.search(r'감소|하락|줄', seg): sign = -1
    if re.search(r'증가|상승|늘', seg): sign = 1 if sign == 0 else sign
    if '비슷' in seg and not nums: return (0.0, np.nan) if '전년' in seg else (np.nan, 0.0)
    has_y, has_p = '전년' in seg, '평년' in seg
    # '전년 대비 8.1% 감소, 평년 대비 13.7% 증가' 처럼 방향이 다른 경우
    parts = re.findall(r'(전년|평년)[^%]*?대비[^%]*?(\d+(?:\.\d+)?)\s*%\s*(증가|감소|상승|하락)', seg)
    if parts:
        y = p = np.nan
        for who, n, d in parts:
            v = float(n) * (1 if d in ('증가', '상승') else -1)
            if who == '전년': y = v
            else: p = v
        if '각각' in seg and len(nums) >= 2 and has_y and has_p:
            y, p = nums[0] * sign, nums[1] * sign
        return (y, p)
    if not nums or sign == 0: return (np.nan, np.nan)
    if has_y and has_p and len(nums) >= 2: return (nums[0] * sign, nums[1] * sign)
    if has_y: return (nums[0] * sign, np.nan)
    if has_p: return (np.nan, nums[0] * sign)
    return (np.nan, np.nan)
rows = []
for bun, items in ITEMS.items():
    f = os.path.join(SRC, f'{bun}_페이지텍스트.csv')
    if not os.path.exists(f): continue
    d = pd.read_csv(f)
    for r in d.itertuples():
        item, season, title = None, '전체', ''
        for line in str(r.텍스트).splitlines():
            L = line.strip()
            if not L: continue
            if not L.startswith(('•', '-', '*', '※', '·')) and len(L) <= 40:
                hit = [it for it in items if it in L.replace(' ', '')]
                if hit:
                    it = max(hit, key=len)
                    if it == '고추' and '건고추' in L: it = '건고추'
                    item, title = it, L
                    s = [v for k, v in SEASON if k in L.replace(' ', '').split(it)[0] + L.replace(' ', '')[:L.replace(' ', '').find(it)]]
                    season = s[0] if s else '전체'
                    if '시설' in L and s and s[0] != '시설': season = s[0] + '(시설)'
                continue
            if item is None or not L.startswith('•'): continue
            body = L.lstrip('•').strip()
            m = re.match(r'(' + '|'.join(re.escape(x) for x in IND) + r')(?:\([^)]*\))?\s*:\s*(.*)', body)
            if not m: continue
            ind, rest = m.group(1), m.group(2)
            ind = {'재배의향면적': '재배(의향)면적', '정식(의향)면적': '재배(의향)면적', '파종(의향)면적': '재배(의향)면적'}.get(ind, ind)
            mv = re.search(NUM, rest)
            val, unit = (np.nan, '')
            if mv:
                unit = mv.group(2); val = kor_num(mv.group(1), unit)
                if unit in ('천 톤',): val *= 1000; unit = '톤'
                if unit in ('만 톤',): val *= 10000; unit = '톤'
            y, p = pct_pair(rest)
            rows.append(dict(분야=bun, 연도=int(r.연도), 발행월=int(r.발행월), 파일=r.파일, 페이지=int(r.페이지), 품목=item, 작형=season, 제목=title,
                             지표=ind, 값=val, 단위=unit, 전년비_pct=y, 평년비_pct=p, 원문=L[:200]))
X = pd.DataFrame(rows, columns=['분야', '연도', '발행월', '파일', '페이지', '품목', '작형', '제목', '지표', '값', '단위', '전년비_pct', '평년비_pct', '원문'])
X['발행'] = X.연도.astype(str) + '-' + X.발행월.astype(str).str.zfill(2)
X = X[(X.전년비_pct.abs() <= 300) | X.전년비_pct.isna()]
os.makedirs(OUT, exist_ok=True)
X.to_csv(os.path.join(OUT, '01_작형별_수급지표_long.csv'), index=False, encoding='utf-8-sig')
W = X.dropna(subset=['전년비_pct']).groupby(['품목', '작형', '지표', '발행']).전년비_pct.median().reset_index()
W.to_csv(os.path.join(OUT, '02_품목_작형_지표_발행월_전년비.csv'), index=False, encoding='utf-8-sig')
print(len(X), '행; 전년비 있는 행', int(X.전년비_pct.notna().sum()))
print(X.dropna(subset=['전년비_pct']).groupby(['품목', '작형']).발행.nunique().unstack(fill_value=0).to_string())
print(X.dropna(subset=['전년비_pct']).groupby('지표').size())

"""실행: python 농업관측월보_전체다운로드.py
추가 설치나 API 키 불필요. 기본값: 사이트에 공개된 모든 분야/모든 연도의 월보 PDF.
ZIP은 분야/연도로 저장. 전처리/압축해제는 하지 않음.
목록만 확인: python 농업관측월보_전체다운로드.py --목록만
농산물만: python 농업관측월보_전체다운로드.py --농산물만
특정 분야: python 농업관측월보_전체다운로드.py --분야 과일
"""
import argparse
import csv
import html
import io
from pathlib import Path
import re
import time
import urllib.parse
import urllib.request
import zipfile

BASE = 'https://aglook.krei.re.kr'
AGRICULTURE = {'엽근채소', '양념채소', '과일', '과채', '버섯', '쌀', '콩', '감자', '국제곡물'}

def fetch(url):
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Referer': BASE + '/main'})
            with urllib.request.urlopen(request, timeout=120) as response:
                return response.read()
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 + attempt)

def links(source):
    return [(html.unescape(u), re.sub('<[^>]+>', '', title).strip())
            for u, title in re.findall(r'<a\b[^>]*href=[\"\x27]([^\"\x27]+)[\"\x27][^>]*>(.*?)</a>', source, re.S | re.I)]

def years(source):
    select = re.search(r'<select\b[^>]*name="queryType"[^>]*>(.*?)</select>', source, re.S)
    if not select:
        raise ValueError('연도 선택 목록을 찾지 못함: 사이트 구조 확인 필요')
    return list(dict.fromkeys(re.findall(r'<option\b[^>]*value="(\d{4})"', select[1])))

def valid_zip(path):
    try:
        with zipfile.ZipFile(path) as z:
            return bool(z.namelist()) and z.testzip() is None
    except (OSError, zipfile.BadZipFile):
        return False

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--목록만', action='store_true')
    parser.add_argument('--농산물만', action='store_true')
    parser.add_argument('--분야', help='예: 과일. 생략하면 전체 분야')
    args = parser.parse_args()
    out = Path(__file__).resolve().parent / '농업관측월보_원본'
    out.mkdir(exist_ok=True)
    rows = []
    def record(category, year, url, status, detail=''):
        rows.append([category, year, url, status, detail])
        with (out / '다운로드_처리내역.csv').open('w', encoding='utf-8-sig', newline='') as f:
            w = csv.writer(f); w.writerow(['분야','연도','공식주소','상태','설명']); w.writerows(rows)
    source = fetch(BASE + '/main/sitemap').decode('utf-8')
    categories = {}
    for url, title in links(source):
        if re.fullmatch(r'/main/uObserveMonth/OVR\d+', url):
            categories.setdefault(url, title)
    if not categories:
        raise ValueError('분야 목록을 찾지 못함. 공식 사이트맵을 확인해 주세요.')
    selected = [(u,t) for u,t in categories.items()
                if (not args.농산물만 or t in AGRICULTURE) and (not args.분야 or t == args.분야)]
    if not selected:
        raise ValueError('해당 분야 없음. 가능한 분야: ' + ', '.join(categories.values()))
    print('수집 분야:', ', '.join(t for _,t in selected), flush=True)
    print('기간: 분야별 사이트 연도 목록 전체. 이미 받은 정상 ZIP은 건너뜀.', flush=True)
    for route, title in selected:
        try:
            page = fetch(BASE + route).decode('utf-8')
            available = years(page)
        except Exception as e:
            record(title, '', BASE + route, '분야조회실패', str(e)); continue
        for year in available:
            page_url = BASE + route + '?queryType=' + year
            try:
                # 실제 해당 연도 페이지에 공개된 ZIP 링크만 사용한다.
                page = fetch(page_url).decode('utf-8')
                urls = list(dict.fromkeys(urllib.parse.urljoin(BASE, u) for u,_ in links(page)
                            if re.search(r'/zipDown/' + year + r'/pdf(?:\?|$)', u)))
                if not urls:
                    record(title, year, page_url, '일괄링크없음', '공식 페이지에서 개별 파일 확인 필요')
                    continue
                for url in urls:
                    folder = out / re.sub(r'[<>:"/\\|?*]', '_', title)
                    folder.mkdir(exist_ok=True)
                    target = folder / (title + '_' + year + '_월보원본.zip')
                    if args.목록만:
                        status = '목록확인'
                    elif valid_zip(target):
                        status = '기존파일정상'
                    else:
                        print('다운로드:', title, year, flush=True)
                        data = fetch(url)
                        with zipfile.ZipFile(io.BytesIO(data)) as z:
                            if not z.namelist() or z.testzip() is not None:
                                raise ValueError('ZIP이 비었거나 손상됨')
                        temp = target.with_suffix('.part')
                        temp.write_bytes(data); temp.replace(target)
                        status = '다운로드완료'
                    record(title, year, url, status)
                    print(title, year, status, flush=True)
                time.sleep(1)
            except Exception as e:
                record(title, year, page_url, '실패', str(e))
                print('실패:', title, year, str(e), flush=True)
    failed = sum(r[3] in ('실패','분야조회실패','일괄링크없음') for r in rows)
    print('종료. 처리', len(rows), '건 / 확인 필요한 항목', failed, '건')
    print('저장 위치:', out)
    print('전체 확보 여부는 다운로드_처리내역.csv의 실패/일괄링크없음 항목을 확인하세요.')

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n중단됨. 다시 실행하면 정상 ZIP은 건너뛰고 이어받습니다.')

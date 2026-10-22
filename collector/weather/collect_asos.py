#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""NongClock | 전국 ASOS 일자료(기간 조회) 수집기

기상청 API허브 공식 1.4 일자료(기간 조회):
https://apihub.kma.go.kr/apiList.do?apiSeq=2
- stn=0: API에서 해당 기간에 제공하는 전체 지점 (고정 66개 목록 아님)
- 자료: 2015-01-01 ~ 2026-10-14 (기본값)
- 월별 원본을 보존하고, 성공적으로 검증한 월은 재실행 시 건너뜀.
- 음수 강수값은 0으로 바꾸지 않으며, 원본과 확인 플래그를 남김.
- Python 3.9+, 표준 라이브러리만 필요. 인증키는 실행 시 입력하거나 환경변수로 받음.

원래 파일: NongClock_ASOS_전국_수집_수정본.py (리눅스 서버용으로 경로·키 읽기만 바꿈)
실행 (보통은 run.py가 대신 실행):
    python collect_asos.py --start 2015-01-01 --end <어제> --out data/raw/asos
    python collect_asos.py --self-test
주의: --start는 반드시 2015-01-01. 통합 CSV(ASOS_일자료_전국통합.csv)를 준 기간으로 다시 만들기 때문에
      이번 달을 시작일로 주면 통합 CSV가 한 달치로 덮어써짐(PC에서 실제로 있었던 사고).
인증키: 환경변수 KMA_APIHUB_KEY (예전 이름 KMA_AUTH_KEY도 됨). 없으면 종료코드 2.
"""
from __future__ import annotations

import argparse
import calendar
import csv
import datetime as dt
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
import wxcommon  # urlopen 호출 수 세기 — urllib import보다 먼저
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from collections import Counter, defaultdict

DATA_URL = wxcommon.KMA_APIHUB_BASE + "/api/typ01/url/kma_sfcdd3.php"
STATION_URL = wxcommon.KMA_APIHUB_BASE + "/api/typ01/url/stn_inf.php"
BASE = wxcommon.data_dir() / "raw" / "asos"
STATION_REFERENCE = wxcommon.REF / "ASOS_관측지점_참고_97개.csv"   # 선택(없어도 됨): 지점명 보완용
DEFAULT_START = "2015-01-01"
DEFAULT_END = (dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date() - dt.timedelta(days=1)).isoformat()  # 한국시간 어제


class AuthError(Exception):
    """인증키 미등록·권한 없음 (HTTP 401/403 등). 재시도하지 않음."""

# KMA 1.4 일자료(기간 조회) 공식 출력변수명
# 원본 변수명 그대로 매칭. 없는 항목을 다른 값으로 추정하지 않음.
FIELDS = {
    "날짜": "TM", "지점": "STN",
    "평균기온": "TA_AVG", "최고기온": "TA_MAX", "최저기온": "TA_MIN",
    "강수량": "RN_DAY", "최다1시간강수": "RN_60M_MAX",
    "평균습도": "HM_AVG", "최저습도": "HM_MIN",
    "평균풍속": "WS_AVG", "최대풍속": "WS_MAX",
    "일조시간": "SS_DAY", "일사량": "SI_DAY",
}
OUTPUT_COLS = list(FIELDS) + ["강수원본값", "강수값상태"]
REQUIRED = {"TM", "STN", "TA_AVG", "TA_MAX", "TA_MIN", "RN_DAY", "HM_AVG", "WS_AVG", "SS_DAY", "SI_DAY"}
OPTIONAL = {"RN_60M_MAX", "HM_MIN", "WS_MAX"}
NUMERIC = set(OUTPUT_COLS) - {"날짜", "지점", "강수원본값", "강수값상태"}
NONNEGATIVE = NUMERIC - {"평균기온", "최고기온", "최저기온"}


def clean_date(s):
    s = s.strip()
    if re.fullmatch(r"\d{8}", s):
        return dt.datetime.strptime(s, "%Y%m%d").date().isoformat()
    if re.fullmatch(r"\d{10,12}", s):
        return dt.datetime.strptime(s[:8], "%Y%m%d").date().isoformat()
    try:
        return dt.date.fromisoformat(s).isoformat()
    except ValueError as e:
        raise ValueError(f"알 수 없는 날짜: {s!r}") from e


def decode_reply(data: bytes):
    for encoding in ("utf-8-sig", "euc-kr", "cp949"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            pass
    raise ValueError("API 응답 인코딩 판별 실패. 수신한 파일을 확인하세요.")


def parse_asos(text: str, begin: dt.date, end: dt.date):
    """공식 변수명 일치 검증. 0mm는 0으로 유지, 음수는 결측 처리 + 원본 기록."""
    lines = text.splitlines()
    # 순수 수치 날짜로 시작하는 행만 데이터로 판단
    data_lines = [ln.split() for ln in lines if ln.strip() and
                  not ln.lstrip().startswith("#") and re.match(r"^\s*\d{8}(?:\d{2,4})?\s+\d+\s", ln)]
    if not data_lines:
        raise ValueError("일자료 데이터 행을 찾지 못함. 인증키/권한/기간/API 오류 가능\n" + text[:500])
    count = Counter(map(len, data_lines))
    width = count.most_common(1)[0][0]
    if len(count) > 1:
        raise ValueError(f"일자료 열 수가 일정하지 않음: {dict(count)} (잘못된 행을 버리지 않음)")

    possible_headers = []
    for ln in lines:
        if not ln.lstrip().startswith("#"):
            continue
        tok = ln.lstrip()[1:].split()
        if (len(tok) == width and tok and tok[0].upper() in {"TM", "YYMMDD", "YYYYMMDD"}
                and len(tok) > 1 and tok[1].upper() in {"STN", "STN_ID"}):
            possible_headers.append(tok)
    if not possible_headers:
        raise ValueError(f"응답의 {width}열에 대응하는 헤더를 찾지 못함. 첫 부분:\n" + "\n".join(lines[:25]))
    hdr = [s.upper() for s in possible_headers[-1]]
    hdr[0] = "TM"
    if hdr[1] == "STN_ID": hdr[1] = "STN"
    # 일부 API 응답은 TA/TA/TA처럼 그룹명만 반복합니다.
    # 이전 파일의 주석에 있는 그룹내 순서를 근거로 제한적으로 지원합니다.
    # 해당 구조를 확정할 수 없는 경우 추정하지 않고 중단합니다.
    index_by_name = defaultdict(list)
    for idx, name in enumerate(hdr):
        index_by_name[name].append(idx)
    group_fallback = {
        "TA_AVG": ("TA", 0), "TA_MAX": ("TA", 1), "TA_MIN": ("TA", 3),
        "RN_DAY": ("RN", 0), "RN_60M_MAX": ("RN", 3),
        "HM_AVG": ("HM", 0), "HM_MIN": ("HM", 1),
        "WS_AVG": ("WS", 0), "WS_MAX": ("WS", 1),
        "SS_DAY": ("SS", 0), "SI_DAY": ("SI", 0),
    }
    positions = {}
    fallback_used = []
    for field in REQUIRED | OPTIONAL:
        if field in index_by_name:
            positions[field] = index_by_name[field][0]
        elif field in group_fallback:
            group, occurrence = group_fallback[field]
            if len(index_by_name[group]) > occurrence:
                positions[field] = index_by_name[group][occurrence]
                fallback_used.append(field)
    missing = sorted(REQUIRED - set(positions))
    if missing:
        raise ValueError("필수 변수명 또는 지원하는 그룹헤더 위치가 없습니다. 임의 추정하지 않습니다. "
                         + ", ".join(missing) + "\n실제 헤더: " + " ".join(hdr))
    if fallback_used:
        print("  [주의] 그룹 반복형 헤더 매핑 사용: " + ", ".join(sorted(fallback_used)), flush=True)

    parsed = []
    seen = set()
    for data in data_lines:
        day = clean_date(data[positions["TM"]])
        d = dt.date.fromisoformat(day)
        if not begin <= d <= end:
            raise ValueError(f"요청기간 바깥 날짜가 수신됨: {day} ({begin}~{end})")
        station = int(data[positions["STN"]])
        key = (day, station)
        if key in seen:
            raise ValueError(f"중복 일자+지점 발견: {key}. API 원본을 검토하세요.")
        seen.add(key)
        row = {"날짜": day, "지점": station}
        for name, field in FIELDS.items():
            if name in ("날짜", "지점"):
                continue
            token = data[positions[field]] if field in positions else ""
            try:
                val = float(token)
            except (ValueError, TypeError):
                val = None
            if val is not None:
                if not (-1e20 < val < 1e20):
                    val = None
                elif name in NONNEGATIVE and val < 0:
                    val = None
                elif name in ("평균기온", "최고기온", "최저기온") and val <= -90:
                    val = None
            row[name] = "" if val is None else val
        rain_token = data[positions["RN_DAY"]]
        row["강수원본값"] = rain_token
        if row["강수량"] != "":
            row["강수값상태"] = "유효_0mm" if row["강수량"] == 0 else "유효_강수"
        else:
            row["강수값상태"] = "음수코드_검증필요" if rain_token.lstrip().startswith("-") else "결측_검증필요"
        parsed.append(row)
    if not parsed:
        raise ValueError("해당 기간 내 관측데이터가 없습니다.")
    return sorted(parsed, key=lambda r: (r["날짜"], r["지점"]))


def download_text(url, params, attempts=4, timeout=120):
    safe_params = {k: v for k, v in params.items() if k != "authKey"}
    for n in range(1, attempts+1):
        try:
            req = Request(url + "?" + urlencode(params), headers={"User-Agent":"NongClock-ASOS-Collector/1.0"})
            with urlopen(req, timeout=timeout) as response:
                text = decode_reply(response.read())
            error_words = ("INVALID AUTH", "SERVICE KEY", "INVALID_KEY", "ERROR: AUTH", "잘못된 인증")
            if any(w in text.upper() for w in error_words):
                raise AuthError(f"API 인증/권한 문제: {text[:250]}")
            return text
        except HTTPError as e:
            if e.code in (401, 403):
                raise AuthError(f"HTTP {e.code} (API허브 활용신청·인증키 확인)") from e
            if n == attempts:
                raise RuntimeError(f"API {safe_params} 다운로드 {attempts}회 실패: {e}") from e
            print(f"  재시도 {n}/{attempts}: HTTP {e.code} | {safe_params}", flush=True)
            time.sleep(2 * n)
        except (URLError, TimeoutError, OSError) as e:
            if n == attempts:
                raise RuntimeError(f"API {safe_params} 다운로드 {attempts}회 실패: {e}") from e
            print(f"  재시도 {n}/{attempts}: {type(e).__name__} | {safe_params}", flush=True)
            time.sleep(2 * n)
    raise AssertionError("unreachable")


def atomic_write(path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix="._nongclock_", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def csv_bytes(rows, fieldnames):
    sio = io.StringIO(newline="")
    writer = csv.DictWriter(sio, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return sio.getvalue().encode("utf-8-sig")


def shasum(data):
    return hashlib.sha256(data).hexdigest()


def months(start, end):
    curr = dt.date(start.year, start.month, 1)
    while curr <= end:
        last = dt.date(curr.year, curr.month, calendar.monthrange(curr.year, curr.month)[1])
        yield max(start, curr), min(last, end)
        curr = (last + dt.timedelta(days=1))


def validated_cached(csv_path, meta_path, st, en):
    if not (csv_path.is_file() and meta_path.is_file()):
        return None
    try:
        m = json.loads(meta_path.read_text(encoding="utf-8"))
        if m.get("start") != st.isoformat() or m.get("end") != en.isoformat():
            return None
        if shasum(csv_path.read_bytes()) != m.get("csv_sha256"):
            return None
        return m
    except (ValueError, OSError):
        return None


def metadata_from_station_reply(txt):
    """지상관측 지점정보: 헤더 설명 아래 지점코드 경도 위도 ... 지점명."""
    results = {}
    for ln in txt.splitlines():
        if ln.lstrip().startswith("#") or not ln.strip():
            continue
        tok = ln.split()
        if len(tok) < 11:
            continue
        try:
            sid, lon, lat = int(tok[0]), float(tok[1]), float(tok[2])
        except ValueError:
            continue
        if not (123 <= lon <= 133 and 32 <= lat <= 40):
            continue
        results[sid] = {"지점": sid, "지점명": tok[10], "위도": lat, "경도": lon}
    return results


def load_station_reference():
    """2026년 이전 별도 수집분 (보조 명칭 사전). 실제 API 요청 지점을 제한하지 않음."""
    if not STATION_REFERENCE.exists():
        return {}
    with STATION_REFERENCE.open(encoding="utf-8-sig", newline="") as f:
        return {int(r["지점"]): r for r in csv.DictReader(f)}


def station_metadata(auth_key, out_dir, end):
    reference = load_station_reference()
    path = out_dir / "관측소" / f"관측지점_{end.isoformat()}.csv"
    if path.exists():
        with path.open(encoding="utf-8-sig", newline="") as f:
            return {**reference, **{int(x["지점"]):x for x in csv.DictReader(f)}}
    try:
        print("  관측지점 메타데이터 조회 (역사적 전체 지점 수와 동일하지 않을 수 있음)", flush=True)
        txt = download_text(STATION_URL, {"inf":"SFC", "stn":"0",
                                           "tm":end.strftime("%Y%m%d")+"1200", "help":"0", "authKey":auth_key})
        stations = metadata_from_station_reply(txt)
        if not stations:
            raise ValueError("지점 메타정보 파싱 결과 0건")
        atomic_write(out_dir/"관측소"/"지점정보_원본.txt", txt.encode("utf-8"))
        atomic_write(path, csv_bytes(sorted(stations.values(),key=lambda x:x["지점"]),["지점","지점명","위도","경도"]))
        print(f"  지점정보 {len(stations)}개 저장 (지점별 관측 시작·종료시점은 별개)")
        return {**reference, **stations}
    except AuthError:
        raise
    except Exception as e:
        print(f"  [주의] 지점명·좌표 조회 실패: {str(e)[:160]} | 기존 참고 지점정보로 보완하며 일자료 계속 수집")
        return reference


def gather_report(out_dir, month_meta, station_lookup, start, end):
    summary=[]
    per_station=defaultdict(lambda:{"first":None,"last":None,"rows":0})
    counters=Counter()
    out_file=out_dir/"ASOS_일자료_전국통합.csv"
    temp_file=out_dir/"._ASOS_전국통합_tmp.csv"
    with temp_file.open("w", newline="",encoding="utf-8-sig") as out:
        writer=csv.DictWriter(out,fieldnames=OUTPUT_COLS,lineterminator="\n")
        writer.writeheader()
        for meta in month_meta:
            path=out_dir/"월별CSV"/f'{meta["month"]}.csv'
            local_stations=set()
            local_days=set()
            count=0
            rain_bad=0
            with path.open(encoding="utf-8-sig",newline="") as f:
                for row in csv.DictReader(f):
                    writer.writerow(row)
                    count+=1
                    st_id=int(row["지점"])
                    local_stations.add(st_id)
                    per_station[st_id]["rows"]+=1
                    first=per_station[st_id]["first"]
                    last=per_station[st_id]["last"]
                    day=row["날짜"]
                    local_days.add(day)
                    if first is None or day<first:per_station[st_id]["first"]=day
                    if last is None or day>last:per_station[st_id]["last"]=day
                    if row["강수값상태"] in ("음수코드_검증필요","결측_검증필요"):
                        rain_bad+=1
                    for col in NUMERIC:
                        if not row[col].strip():
                            counters[col]+=1
            if count!=meta["rows"] or len(local_stations)!=meta["stations"]:
                raise ValueError(f'월별 자료 검증 실패: {meta["month"]} - 재수집 또는 파일 확인 필요')
            period_days = (dt.date.fromisoformat(meta["end"])-dt.date.fromisoformat(meta["start"])).days+1
            summary.append({"월":meta["month"],"시작":meta["start"],"종료":meta["end"],
                            "기대날짜수":period_days,"관측된날짜수":len(local_days),
                            "전국관측행이없는날짜수":period_days-len(local_days),
                            "데이터행":count,"서로다른지점":len(local_stations),
                            "강수결측확인필요":rain_bad})
    os.replace(temp_file,out_file)
    st_rows=[]
    for st_id, info in sorted(per_station.items()):
        st=station_lookup.get(st_id,{})
        st_rows.append({"지점":st_id,"지점명":st.get("지점명",""),
                        "위도":st.get("위도",""),"경도":st.get("경도",""),
                        "관측첫날":info["first"],"관측마지막날":info["last"],"수집행수":info["rows"],
                        "지점정보확인": "확인" if st else "미확인(과거폐쇄등가능)"})
    atomic_write(out_dir/"월별_수집검증.csv",csv_bytes(summary,list(summary[0].keys())))
    atomic_write(out_dir/"지점별_수집검증.csv",csv_bytes(st_rows,list(st_rows[0].keys())))
    rows_total=sum(x["데이터행"] for x in summary)
    cts={k:round(v/rows_total*100,2) for k,v in counters.items()}
    report={"요청기간":f"{start}~{end}","방식":"ASOS 일자료 stn=0; 전체지점 API 요청",
            "수집월수":len(summary),"전국관측행이없는전체날짜":sum(x["전국관측행이없는날짜수"] for x in summary),"데이터행":rows_total,"실제관측지점수(기간내합집합)":len(per_station),
            "기준일지점정보수":len(station_lookup),"관측지점명정보없는코드":sorted(set(per_station)-set(station_lookup)),
            "변수별결측비율_퍼센트":cts,"강수값처리":"0은 무강수로 유지, 음수는 빈값으로 두고 강수원본값+상태 보존",
            "주의":"매 날짜 모든 관측소가 관측하지 않을 수 있음. 누락값 보간하지 않음. 관측소 위치는 조회 기준일 현재 정보.",
            "생성파일":"ASOS_일자료_전국통합.csv"}
    atomic_write(out_dir/"수집결과_요약.json",json.dumps(report,ensure_ascii=False,indent=2).encode("utf-8"))
    print(f"\n완료: {rows_total:,}행 / 실제 지점 {len(per_station)}곳 / 수집 {len(summary)}개월")
    print(f"통합 CSV: {out_file}")
    print(f"검증 보고서: {out_dir/'수집결과_요약.json'}")
    if not station_lookup:
        print("주의: 지점 메타데이터 조회 실패, 지점명/좌표는 비어 있습니다. 지점번호는 모두 보존했습니다.")


def run(start, end, key, out_dir, pause):
    out_dir.mkdir(parents=True, exist_ok=True)
    month_meta=[]
    blocks=list(months(start,end))
    print(f"전국 ASOS 조회 {start}~{end} | {len(blocks)}개월 | 지점=0(전체)")
    station_lookup=station_metadata(key,out_dir,end)
    for idx,(st,en) in enumerate(blocks,1):
        tag=st.strftime("%Y-%m")
        raw_path=out_dir/"원본"/f"{tag}.txt.gz"
        csv_path=out_dir/"월별CSV"/f"{tag}.csv"
        meta_path=out_dir/"월별CSV"/f"{tag}.meta.json"
        previous=validated_cached(csv_path,meta_path,st,en)
        if previous:
            print(f"[{idx}/{len(blocks)}] {tag}: 검증된 저장분 건너뜀 ({previous['rows']:,}행 / {previous['stations']}곳)",flush=True)
            month_meta.append(previous)
            continue
        print(f"[{idx}/{len(blocks)}] {tag} {st}~{en}: 다운로드",flush=True)
        # 서버판 수정: 예전 원본은 같은 기간(meta 시작·끝 일치)일 때만 다시 씀.
        # (이번 달처럼 끝 날짜가 바뀐 달은 원본을 새로 받아야 새 날짜가 들어옴)
        old_meta=None
        if meta_path.is_file():
            try: old_meta=json.loads(meta_path.read_text(encoding="utf-8"))
            except (ValueError, OSError): old_meta=None
        same_range=old_meta is None or (old_meta.get("start")==st.isoformat() and old_meta.get("end")==en.isoformat())
        downloaded=False
        if raw_path.exists() and same_range:
            with gzip.open(raw_path,"rt",encoding="utf-8") as f:
                text=f.read()
            print("  원본이 이미 있어 네트워크 요청 없이 재전처리",flush=True)
        else:
            text=download_text(DATA_URL,{"tm1":st.strftime("%Y%m%d"),"tm2":en.strftime("%Y%m%d"),
                                         "stn":"0","help":"0","authKey":key})
            downloaded=True
        try:
            rows=parse_asos(text,st,en)
        except Exception as e:
            error_path=out_dir / "오류확인" / f"{tag}.txt"
            atomic_write(error_path,text.encode("utf-8"))
            raise RuntimeError(f"{tag} 응답 형식/내용 검증 실패: {e}\n오류 원본 저장: {error_path}") from e
        # 원본과 CSV 보존. 한 달 파일이 완성된 경우에만 메타 기록.
        if downloaded or not raw_path.exists():
            atomic_write(raw_path,gzip.compress(text.encode("utf-8")))
        content=csv_bytes(rows,OUTPUT_COLS)
        atomic_write(csv_path,content)
        month={"month":tag,"start":st.isoformat(),"end":en.isoformat(),
               "rows":len(rows),"stations":len(set(x["지점"] for x in rows)),
               "csv_sha256":shasum(content)}
        atomic_write(meta_path,json.dumps(month,ensure_ascii=False,indent=2).encode("utf-8"))
        month_meta.append(month)
        print(f"  저장 {len(rows):,}행 / 관측지점 {month['stations']}곳",flush=True)
        if idx<len(blocks):time.sleep(pause)
    gather_report(out_dir,month_meta,station_lookup,start,end)


def self_test():
    from tempfile import TemporaryDirectory
    demo=("# 설명\n"
          "# TM STN WS_AVG WS_MAX TA_AVG TA_MAX TA_MIN HM_AVG HM_MIN SS_DAY SI_DAY RN_DAY RN_60M_MAX\n"
          "20150101 90 3.1 6.2 -5.2 0.3 -11.2 44 20 4.2 12.3 0.0 -9\n"
          "20150101 108 1.2 2.2 -2.2 1 -6.2 52 30 1.0 -9 -9 -9\n"
          "20150102 90 2.1 5.3 -2.2 2.3 -8.1 48 22 5.6 13.1 7.3 5.0\n")
    rows=parse_asos(demo,dt.date(2015,1,1),dt.date(2015,1,2))
    assert len(rows)==3 and rows[0]["강수량"]==0.0
    assert rows[1]["강수량"]=="" and rows[1]["강수원본값"]=="-9"
    assert rows[1]["일사량"]=="" and rows[2]["강수량"]==7.3
    with TemporaryDirectory() as tmp:
        root=Path(tmp)
        csvdata=csv_bytes(rows,OUTPUT_COLS)
        atomic_write(root/"월별CSV"/"2015-01.csv",csvdata)
        meta={"month":"2015-01","start":"2015-01-01","end":"2015-01-02",
              "rows":3,"stations":2,"csv_sha256":shasum(csvdata)}
        atomic_write(root/"월별CSV"/"2015-01.meta.json",json.dumps(meta).encode())
        assert validated_cached(root/"월별CSV"/"2015-01.csv",root/"월별CSV"/"2015-01.meta.json",
                                dt.date(2015,1,1),dt.date(2015,1,2))
        gather_report(root,[meta],{90:{"지점명":"속초","위도":"38.25","경도":"128.56"}},
                      dt.date(2015,1,1),dt.date(2015,1,2))
        assert (root/"ASOS_일자료_전국통합.csv").is_file()
    print("셀프 테스트 통과: 헤더 매핑/무강수/음수결측/일사량/중복검증/저장/재개/통합")


def main():
    p=argparse.ArgumentParser(description="NongClock 전국 기상청 ASOS 일자료 자동 다운로드")
    p.add_argument("--start",default=DEFAULT_START,help="시작일 YYYY-MM-DD (기본 2015-01-01)")
    p.add_argument("--end",default=DEFAULT_END,help="종료일 YYYY-MM-DD (기본 2026-10-14)")
    p.add_argument("--out",default=str(BASE),help="결과 폴더")
    p.add_argument("--pause",type=float,default=0.7,help="월별 API 요청 사이 대기 초")
    p.add_argument("--self-test",action="store_true",help="API 호출 없이 예제 자료로 프로그램 검증")
    a=p.parse_args()
    if a.self_test:
        self_test()
        return
    try:
        start,end=dt.date.fromisoformat(a.start),dt.date.fromisoformat(a.end)
    except ValueError as e:
        p.error(f"날짜 형식 오류: {e}")
    if start>end:
        p.error("시작일이 종료일보다 늦습니다.")
    if end>dt.date.today():
        p.error("종료일이 컴퓨터 현재 날짜보다 미래입니다.")
    wxcommon.start()
    auth_key=wxcommon.get_key("KMA_APIHUB_KEY",("KMA_AUTH_KEY",))
    if not auth_key:
        wxcommon.exit_nokey("KMA_APIHUB_KEY")
    out_dir=Path(a.out).resolve()
    before=wxcommon.count_csv_rows(out_dir/"ASOS_일자료_전국통합.csv")
    try:
        run(start,end,auth_key,out_dir,max(0,a.pause))
    except AuthError as e:
        wxcommon.exit_auth(e)
    except (Exception,KeyboardInterrupt) as e:
        print(f"\n중단: {e}\n다시 실행하면 성공적으로 완료된 월부터 이어받습니다.",file=sys.stderr, flush=True)
        wxcommon.error(f"ASOS 중단: {e}")
        sys.exit(1)
    finally:
        # 추가 행 = 통합 CSV 행 수(실행 후 - 실행 전)
        wxcommon.STATS["added"]=wxcommon.count_csv_rows(out_dir/"ASOS_일자료_전국통합.csv")-before

if __name__=="__main__":
    main()

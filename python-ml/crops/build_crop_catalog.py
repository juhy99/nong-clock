# -*- coding: utf-8 -*-
"""작물 추천용 작물 표 만들기 (11-13) → shared/crops.json  (ml-api 작물 추천이 읽음)

  python python-ml/crops/build_crop_catalog.py                      # 기본 경로
  python python-ml/crops/build_crop_catalog.py --data D:\\nong-clock-data --out shared/crops.json

무엇을 어디서 가져오나 (손으로 넣는 숫자는 crop_map.csv 의 대응·보관 일수뿐)
  ① 심는 때·수확 때  농사로 재배력 (02_전처리/21_농사로_재배력_생육온도): 01 작형별 시기 · 09 공식도서 확인(감자·고구마·콩) · 04 달력 보조(옥수수·멜론·과수)
     1년 = 36순(1월 상순 = 1). 순의 첫날·끝날로 날짜를 잡음 → 대략값(±10일), 전국 표준 달력
  ② 10a당 수량·경영비·농가수취가격  농진청 농산물소득조사 2020~2024 중 최근 3개 해 평균 (02_전처리/16_…/02_소득_핵심_연도x작목.csv)
     양파·마늘·쌀 = 통계청 농축산물생산비조사 (25_…/A1), 콩 = A3. 최근 3개 해 평균
     경영비에서 토지임차료(조사 평균)는 뺌 — 화면에서 사용자가 자기 임대료를 넣으므로 두 번 더하지 않게 (통계청 자료는 임차료 칸이 없어 그대로)
  ③ 도매가 → 농가가 받는 값 비율(farm_ratio)  = 조사 농가수취가격 ÷ 그 해 수확 달들의 전국 도매 평균가(DB price_daily 전국·ALL, 금액 합 ÷ 물량 합)
     를 조사 해마다 구해 평균. 조사 줄(예: 시설상추)마다 하나 — 그 줄을 쓰는 작형들의 수확 달을 모두 합친 달로. 0.4~1.3 밖이면 자름.
     추천 계산의 예상 수취가 = 예측 도매가 × 이 비율 (계절 가격 차이는 예측 도매가에 그대로 남음)
  ④ 평년 월별 도매가(normal_price)  2021~2025 같은 달 금액÷물량의 해 평균, 범위 = 그 5해의 최저·최고. 물량이 가장 많은 달의 2% 미만인 달은 비움
     DB 예측이 없을 때(예측 표에 없는 날 · DB 없이 실행)만 씀
계산 규칙 (심는 날 → 수확)
  - 한 번 수확(multi = 0): 심는 기간 첫날에 심으면 수확 기간 첫날부터, 끝날에 심으면 수확 기간 끝날에 끝나게 사이를 직선으로. 한 번 심은 것의 수확은 14일 동안 (가정)
    심고 수확까지 최소 30일 (가정)
  - 여러 번 수확(multi = 1, 과채·딸기·부추·상추): 심고 첫 수확까지 = 수확 기간 첫날 − 심는 기간 첫날, 마지막 수확 = 수확 기간 끝날
"""
import argparse
import csv
import datetime as dt
import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
Y0 = 2026  # 날짜 계산용 평년 (윤년 아님)
SINGLE_HARVEST_DAYS = 14
MIN_DAYS = 30
RATIO_LO, RATIO_HI = 0.4, 1.3
NORMAL_YEARS = range(2021, 2026)
THIN = 0.02
LAND = {"open": "노지", "house": "시설", "paddy": "논", "orchard": "과수원"}
EXTRA_EMOJI = {"rice": "🌾", "soybean": "🫘"}
PH_MAP = {  # 작물 코드 → shared/soil_ph.json 의 조건표 이름
    "onion": "양파", "garlic": "마늘", "radish": "무", "napa_cabbage": "배추(봄동·얼갈이)", "cabbage": "양배추·적채", "green_onion": "대파",
    "scallion": "쪽파(실파)", "potato": "감자", "sweet_potato": "고구마(고구마순)", "carrot": "당근", "spinach": "시금치", "watermelon": "수박",
    "corn": "옥수수", "tomato": "토마토·방울토마토", "cherry_tomato": "토마토·방울토마토", "cucumber": "오이", "eggplant": "가지",
    "green_chili": "고추(풋·꽈리·홍고추)", "paprika": "파프리카·피망", "strawberry": "딸기", "korean_melon": "참외", "melon": "멜론",
    "lettuce": "상추", "chive": "부추", "squash": "호박", "soybean": "콩",
}


def sun_start(n):  # 순번 1~36 → (월, 일) 첫날
    n = int(n); return (n - 1) // 3 + 1, (1, 11, 21)[(n - 1) % 3]


def sun_end(n):
    n = int(n); m = (n - 1) // 3 + 1; k = (n - 1) % 3
    return (m, (10, 20)[k]) if k < 2 else (m, (dt.date(Y0 + (m == 12), m % 12 + 1, 1) - dt.timedelta(1)).day)


def doy(md):
    return (dt.date(Y0, *md) - dt.date(Y0, 1, 1)).days


def gap(a, b):  # a → b 까지 날 수 (해를 넘기면 +365)
    return (doy(b) - doy(a)) % 365


def months_between(hs, he):  # 수확 순번 구간이 걸치는 달들
    ms, m, e = [], (int(hs) - 1) // 3 + 1, (int(he) - 1) // 3 + 1
    while True:
        ms.append(m)
        if m == e:
            return ms
        m = m % 12 + 1


def num(v):
    return None if v is None or (isinstance(v, float) and pd.isna(v)) or v == "" else float(v)


class Data:
    def __init__(self, root: Path, tables: Path):
        p = root / "02_전처리"
        self.n01 = pd.read_csv(p / "21_농사로_재배력_생육온도" / "01_작목작형별_재배일정_요약.csv")
        self.n04 = pd.read_csv(p / "21_농사로_재배력_생육온도" / "04_달력기반_파종수확_보조.csv")
        self.n09 = pd.read_csv(p / "21_농사로_재배력_생육온도" / "09_주요5품목_작형시기_공식도서확인.csv")
        self.rda = pd.read_csv(p / "16_농산물소득조사_2002_2024" / "02_소득_핵심_연도x작목.csv")
        self.a1 = pd.read_csv(p / "25_생산비_저장_수수료_재배력" / "A1_생산비소득_4품목_전국_연도별.csv")
        self.a3 = pd.read_csv(p / "25_생산비_저장_수수료_재배력" / "A3_콩_보리_참깨_생산비소득_전국_연도별.csv")
        self.month = self._national(tables)

    @staticmethod
    def _national(tables: Path):
        """전국 · ALL 등급 월별 (금액, 물량). price_daily.csv 가 커서 조각으로 읽음. --price-cache 로 미리 거른 파일을 줄 수도"""
        parts = []
        for ch in pd.read_csv(tables, usecols=["date", "market_code", "item_code", "grade", "volume_kg", "amount_won"], chunksize=1_000_000,
                              dtype={"market_code": str}):
            ch = ch[(ch.market_code == "national") & (ch.grade == "ALL")]
            if len(ch):
                parts.append(ch[["date", "item_code", "volume_kg", "amount_won"]])
        d = pd.concat(parts); d["y"] = d.date.str[:4].astype(int); d["m"] = d.date.str[5:7].astype(int)
        return d.groupby(["item_code", "y", "m"])[["amount_won", "volume_kg"]].sum()

    # ── ① 시기 ──
    def schedule(self, r):
        src, hs, he, ps, pe = r["sched_src"], num(r["hs"]), num(r["he"]), num(r["ps"]), num(r["pe"])
        if src == "n01":
            x = self.n01[(self.n01.작목 == r["sched_crop"]) & (self.n01.작형 == r["sched_cropping"])]
            if len(x) != 1:
                raise SystemExit(f"재배력 01 에서 못 찾음: {r['sched_crop']} | {r['sched_cropping']} ({len(x)}줄)")
            x = x.iloc[0]; st = "정식" if r["stage"] == "정식" else "파종"
            ps, pe = ps or num(x[f"{st}_시작순번"]), pe or num(x[f"{st}_끝순번"])
            hs, he = hs or num(x["수확_시작순번"]), he or num(x["수확_끝순번"])
            where = f"농사로 재배력 「{r['sched_crop']} · {r['sched_cropping']}」 ({st})"
        elif src == "n09":
            x = self.n09[(self.n09.품목 == r["sched_crop"]) & (self.n09.작형 == r["sched_cropping"])]
            if r["sched_region"]:
                x = x[x.지역_지대.astype(str).str.contains(r["sched_region"])]
            if len(x) != 1:
                raise SystemExit(f"재배력 09 에서 못 찾음: {r['sched_crop']} | {r['sched_cropping']} ({len(x)}줄)")
            x = x.iloc[0]
            ps, pe = ps or num(x["심기_시작순번"]), pe or num(x["심기_끝순번"])
            hs, he = hs or num(x["수확_시작순번"]), he or num(x["수확_끝순번"])
            where = f"농업기술길잡이 「{r['sched_crop']} · {r['sched_cropping']}」 ({x['지역_지대']})"
        elif src == "n04":
            x = self.n04[self.n04.작목 == r["sched_crop"]]
            x = x[x.작형 == r["sched_cropping"]] if r["sched_cropping"] else x[x.작형.isna()] if x.작형.isna().any() else x
            if len(x) != 1:
                raise SystemExit(f"재배력 04 에서 못 찾음: {r['sched_crop']} | {r['sched_cropping']} ({len(x)}줄)")
            x = x.iloc[0]
            ps, pe = ps or num(x["달력_파종시작순번"]), pe or num(x["달력_파종끝순번"])
            hs, he = hs or num(x["달력_수확시작순번"]), he or num(x["달력_수확끝순번"])
            where = f"농사로 재배력 달력 「{r['sched_crop']}{' · ' + r['sched_cropping'] if r['sched_cropping'] else ''}」"
        else:
            where = {"배": "농사로 재배력 「배」 조생~만생종", "벼": "이앙: 농업기술길잡이 벼 중만생종 이앙적기 · 수확: 추정"}.get(r["sched_crop"], "직접 넣음 (추정)")
        return ps, pe, hs, he, where

    # ── ② 수량·경영비 ──
    def econ(self, r):
        src, row = r["econ_src"], r["econ_row"]
        if src == "rda":
            x = self.rda[(self.rda.작목_표준 == row) & self.rda.연도.between(2020, 2024)].sort_values("연도").tail(3)
            if x.empty:
                raise SystemExit(f"소득조사 2020~2024 에 없음: {row}")
            rent = x.토지임차료_원.fillna(0)
            return dict(row=row, source="농진청 농산물소득조사", years=[int(v) for v in x.연도], kg=x.주산물수량_kg.mean(), cost=x.경영비_원.mean(), rent=rent.mean(),
                        price={int(y): float(p) for y, p in zip(x.연도, x.농가수취가격_원kg)}, revenue=x.총수입_원.mean(), income=x.소득_원.mean())
        if src == "kostat":
            x = self.a1[self.a1.품목 == row].sort_values("연도").tail(3)
            return dict(row=row, source="통계청 농축산물생산비조사", years=[int(v) for v in x.연도], kg=x.주산물_10a당_kg.mean(), cost=x.경영비_10a당_원.mean(), rent=0.0,
                        price={int(y): float(p) for y, p in zip(x.연도, x.kg당_수취가격_원)}, revenue=x.총수입_10a당_원.mean(), income=x.소득_10a당_원.mean())
        if src == "kostat_soy":
            x = self.a3[self.a3.품목 == row].sort_values("연도").tail(3)
            return dict(row=row, source="통계청 농축산물생산비조사", years=[int(v) for v in x.연도], kg=x.주산물_10a당_kg.mean(), cost=x.경영비_10a당_원.mean(), rent=0.0,
                        price={int(y): float(a / k) for y, a, k in zip(x.연도, x.총수입_10a당_원, x.주산물_10a당_kg)}, revenue=x.총수입_10a당_원.mean(), income=x.소득_10a당_원.mean())
        raise SystemExit(f"econ_src 모름: {src}")

    # ── ③ 도매가 → 농가 수취가 비율 ──
    def farm_ratio(self, code, months, price_by_year):
        ks = []
        for y, p in price_by_year.items():
            a = v = 0.0
            for m in months:
                if (code, y, m) in self.month.index:
                    a += self.month.loc[(code, y, m), "amount_won"]; v += self.month.loc[(code, y, m), "volume_kg"]
            if v > 0 and p > 0:
                ks.append(p / (a / v))
        if not ks:
            return None, None
        raw = sum(ks) / len(ks)
        return round(min(RATIO_HI, max(RATIO_LO, raw)), 3), round(raw, 3)

    # ── ④ 평년 월별 도매가 ──
    def normal(self, code):
        if code not in self.month.index.get_level_values(0):
            return None
        d = self.month.loc[code].reset_index(); d = d[d.y.isin(NORMAL_YEARS) & (d.volume_kg > 0)]
        d["p"] = d.amount_won / d.volume_kg
        vol = d.groupby("m").volume_kg.mean(); top = vol.max() if len(vol) else 0
        out = {"price": [], "low": [], "high": []}
        for m in range(1, 13):
            x = d[d.m == m]
            if x.empty or vol.get(m, 0) < top * THIN:
                for k in out: out[k].append(None)
            else:
                out["price"].append(round(x.p.mean())); out["low"].append(round(x.p.min())); out["high"].append(round(x.p.max()))
        return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=r"D:\nong-clock-data", help="자료 폴더 맨 위")
    ap.add_argument("--tables", default="", help="price_daily.csv (기본: <data>/05_DB적재/data/tables/price_daily.csv)")
    ap.add_argument("--price-cache", default="", help="전국·ALL 줄만 미리 거른 price_daily (있으면 이걸 읽음, 빠름)")
    ap.add_argument("--map", default=str(HERE / "crop_map.csv"))
    ap.add_argument("--out", default=str(REPO / "shared" / "crops.json"))
    a = ap.parse_args()
    root = Path(a.data)
    tables = Path(a.price_cache or a.tables or root / "05_DB적재" / "data" / "tables" / "price_daily.csv")
    D = Data(root, tables)
    items = {i["code"]: i for i in json.load(open(REPO / "shared" / "items50.json", encoding="utf-8"))["items"]}
    rows = list(csv.DictReader(open(a.map, encoding="utf-8-sig")))
    crops, order, report = {}, [], []
    # ③ 비율은 조사 줄(작물 × econ_row)마다 하나: 그 줄을 쓰는 작형들의 수확 달을 모두 합쳐서 구함.
    #    조사 가격이 1년(또는 그 작형 철) 평균이라, 작형마다 따로 나누면 비싼 철일수록 비율이 낮아져 계절 가격 차이가 지워짐
    union = {}
    for r in rows:
        _, _, hs, he, _ = D.schedule(r)
        union.setdefault((r["code"], r["econ_row"]), set()).update(months_between(hs, he) if hs and he else range(1, 13))
    for r in rows:
        code = r["code"]
        if code not in crops:
            in50 = code in items
            crops[code] = dict(code=code, name=r["name"], emoji=items[code]["emoji"] if in50 else EXTRA_EMOJI.get(code, "🌱"),
                               land_types=[], price_source="forecast" if in50 else "survey", perennial_note=None, harvest_months=None,
                               soil_ph_name=PH_MAP.get(code), rda=None, normal=D.normal(code) if in50 else None, survey_price=None, croppings=[])
            order.append(code)
        c = crops[code]
        ps, pe, hs, he, where = D.schedule(r)
        e = D.econ(r)
        months = months_between(hs, he) if hs and he else list(range(1, 13))
        k, kraw = D.farm_ratio(code, sorted(union[(code, r["econ_row"])]), e["price"]) if c["price_source"] == "forecast" else (None, None)
        price3 = sum(e["price"].values()) / len(e["price"])
        rda = dict(row=e["row"], source=e["source"], years=e["years"], revenue=round(e["revenue"]), cost=round(e["cost"]), income=round(e["income"]),
                   kg=round(e["kg"]), price=round(price3), land_rent=round(e["rent"]))
        if c["rda"] is None:
            c["rda"] = rda
        if c["price_source"] == "survey":
            c["survey_price"] = round(price3)
        if r["land"] == "orchard":  # 다년생: 추천 계산은 안 하고 정보만
            c["land_types"] = ["orchard"]
            c["harvest_months"] = [months[0], months[-1]]
            c["perennial_note"] = f"나무를 심고 몇 해 뒤부터 매년 {months[0]}~{months[-1]}월에 수확해요 (수확 시기: {where})"
            c["farm_ratio"] = k
            report.append((r["name"], "과수", "-", "-", "-", rda["kg"], round(rda["cost"] / 1e4), rda["price"], k, kraw))
            continue
        if None in (ps, pe, hs, he):
            raise SystemExit(f"시기 값이 비어 있음: {r['name']} {r['cropping']} ps={ps} pe={pe} hs={hs} he={he}")
        pf, pt, h0, h1 = sun_start(ps), sun_end(pe), sun_start(hs), sun_end(he)
        multi = r["multi"] == "1"
        if multi:
            d0 = d1 = max(MIN_DAYS, gap(pf, h0)); hd = None
        else:
            hd = min(SINGLE_HARVEST_DAYS, max(7, gap(h0, h1)))
            d0 = max(MIN_DAYS, gap(pf, h0)); d1 = gap(pt, h1) - hd
            if d1 < MIN_DAYS or d1 > 330:
                d1 = d0
        if r["land"] not in c["land_types"]:
            c["land_types"].append(r["land"])
        est = ["storage_days"] + (["schedule"] if r["sched_src"] in ("manual", "n04") else [])
        c["croppings"].append(dict(
            name=r["cropping"], land=r["land"], plant_from=list(pf), plant_to=list(pt), harvest_from=list(h0), harvest_to=list(h1),
            days_first=int(d0), days_last=int(d1), harvest_days=hd, multi_harvest=multi,
            yield_t_per_10a=round(e["kg"] / 1000, 3), cost_per_10a=round(e["cost"] - e["rent"]), cost_survey_per_10a=round(e["cost"]), land_rent_in_survey=round(e["rent"]),
            farm_ratio=k, farm_ratio_raw=kraw, storage_days=int(r["storage_days"] or 0),
            source=dict(schedule=where, econ=f"{e['source']} 「{e['row']}」 {e['years'][0]}~{e['years'][-1]} 평균"), estimated=est, rda=rda))
        report.append((r["name"], r["cropping"], f"{pf[0]}/{pf[1]}~{pt[0]}/{pt[1]}", f"{h0[0]}/{h0[1]}~{h1[0]}/{h1[1]}", f"{d0}~{d1}일", rda["kg"], round((e["cost"] - e["rent"]) / 1e4), rda["price"], k, kraw))
    out = dict(
        _about="작물 추천용 작물 표. python-ml/crops/build_crop_catalog.py 가 만듦 (손으로 고치지 말 것 — crop_map.csv 를 고치고 다시 만들기). "
               "심는 때·수확 때 = 농사로 재배력(전국 표준 달력, 순 단위라 ±10일), 수량·경영비 = 농진청 농산물소득조사·통계청 생산비조사 최근 3개 해 평균(전국), "
               "farm_ratio = 조사 농가수취가격 ÷ 같은 해 수확 달 전국 도매 평균가, normal = 2021~2025 같은 달 전국 도매 평균(최저·최고). "
               "storage_days 는 추정. 농사로 자료는 공공누리 제4유형(출처표시·상업적 이용금지·변경금지)",
        built_at=dt.date.today().isoformat(), land_types=LAND,
        rules=dict(single_harvest_days=SINGLE_HARVEST_DAYS, min_days=MIN_DAYS, farm_ratio_range=[RATIO_LO, RATIO_HI], normal_years=[NORMAL_YEARS[0], NORMAL_YEARS[-1]]),
        crops=[crops[k] for k in order])
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    R = pd.DataFrame(report, columns=["작물", "작형", "심는 때", "수확 때", "심고 수확까지", "수량 kg/10a", "경영비(임차료 뺌) 만원", "수취가 원/kg", "농가/도매 비율", "자르기 전"])
    pd.set_option("display.width", 250); pd.set_option("display.max_rows", 200)
    print(R.to_string(index=False))
    print(f"\n→ {a.out}: 작물 {len(order)}개 (추천 계산 {sum(1 for c in crops.values() if c['croppings'])} · 과수 정보만 {sum(1 for c in crops.values() if not c['croppings'])}), 작형 {sum(len(c['croppings']) for c in crops.values())}개")


if __name__ == "__main__":
    sys.exit(main())

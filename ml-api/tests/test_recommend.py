"""작물 추천 (11-13 실제 자료: shared/crops.json + DB 예측 표). DB 없이 돌리면 가격 = 평년 도매가 × 농가 수취 비율"""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.crop_catalog import CROPS
from app.main import app
from app.services import crop_prices, recommender

client = TestClient(app)
TODAY = date.today()


def _post(lands, start=TODAY, region="경기", **kw):
    return client.post("/recommend/crops", json={"region": region, "lands": lands, "start_date": start.isoformat(), **kw})


def _first_window(code, land=None):
    """그 작물이 심을 수 있는 가장 가까운 날 (오늘 포함)"""
    crop = CROPS[code]
    for k in range(366):
        d = TODAY + timedelta(days=k)
        if any(c.in_window(d) and (land is None or c.land == land) for c in crop.croppings):
            return d
    raise AssertionError(code)


# ── 작물 표 ──
def test_crop_list_from_catalog():
    crops = client.get("/recommend/crops").json()
    by = {c["code"]: c for c in crops}
    assert len(crops) == 34 and {"tomato", "watermelon", "rice", "soybean", "apple"} <= set(by)
    assert by["watermelon"]["land_types"] == ["open", "house"] and by["watermelon"]["land_type"] == "open"
    assert by["apple"]["perennial"] and by["apple"]["land_type"] == "orchard"


def test_schedule_follows_planting_window():
    onion = CROPS["onion"].croppings[0]  # 10/11~11/20 정식, 첫날 172일 · 끝날 198일
    h0, h1 = onion.schedule(date(2026, 10, 11))
    assert (h0 - date(2026, 10, 11)).days == onion.days_first and (h1 - h0).days == 14
    h0, _ = onion.schedule(date(2026, 11, 20))
    assert (h0 - date(2026, 11, 20)).days == onion.days_last
    tom = next(c for c in CROPS["tomato"].croppings if c.name == "반촉성재배")  # 12/21~2/10: 해를 넘는 심는 기간
    assert tom.in_window(date(2027, 1, 5)) and not tom.in_window(date(2027, 3, 1))
    h0, h1 = tom.schedule(date(2027, 1, 5))  # 여러 번 수확: 수확 기간 끝날(6/10)까지
    assert h0 < h1 and (h1.month, h1.day) == tom.harvest_to


# ── 추천 ──
def test_recommend_sorted_consistent_and_real_sources():
    d = _first_window("tomato", "house")
    res = _post([{"type": "open", "area_pyeong": 1200}, {"type": "house", "area_pyeong": 600}], start=d)
    assert res.status_code == 200
    out = res.json()
    rs = out["results"]
    assert rs and "tomato" in {o["crop"] for o in rs}
    for t in ("main", None, "rare"):   # 11-18: 주산지 묶음 안에서는 소득 높은 순
        margins = [o["margin"] for o in rs if not o["demoted"] and o["region_tier"] == t]
        assert margins == sorted(margins, reverse=True)
    for o in rs:
        assert o["land_type"] in ("open", "house")
        assert abs(o["revenue"] - o["cost"] - o["margin"]) <= 1
        assert o["plant_date"] == d.isoformat() and o["harvest_start"] <= o["harvest_end"]
        assert o["econ_source"] and o["schedule_source"] and o["rda"]["years"]
        assert o["margin_low"] <= o["margin"] <= o["margin_high"]
        assert sum(o["price_basis"].values()) == pytest.approx(1, abs=0.01)
    assert "rice" not in {o["crop"] for o in rs}  # 논을 고르지 않음
    assert "작물표" in out["model_version"]


def test_one_result_per_crop_best_cropping_and_land():
    d = _first_window("watermelon", "house")
    rs = _post([{"type": "open", "area_pyeong": 900}, {"type": "house", "area_pyeong": 900}], start=d).json()["results"]
    codes = [o["crop"] for o in rs]
    assert len(codes) == len(set(codes))


def test_cost_uses_survey_cost_without_rent_plus_user_rent():
    d = _first_window("onion")
    o = next(x for x in _post([{"type": "open", "area_pyeong": 302.5, "land_rent": 50}], start=d).json()["results"] if x["crop"] == "onion")
    c = CROPS["onion"].croppings[0]
    # 11-16: 1년 임대료 50만원을 재배 기간만큼 (예전엔 작기마다 1년치 전부)
    assert o["land_rent_year"] == 500_000 and 0 < o["rent_days"] <= 365
    assert o["base_cost"] == pytest.approx(c.cost_per_10a, abs=1) and o["land_rent"] == pytest.approx(500_000 * o["rent_days"] / 365, abs=1)
    assert o["cost"] == pytest.approx(o["base_cost"] + o["land_rent"], abs=1)
    assert o["yield_t"] == pytest.approx(c.yield_t_per_10a, abs=0.01)


def test_recommend_start_date_within_one_year():
    body = [{"type": "open", "area_pyeong": 100}]
    assert _post(body, start=TODAY + timedelta(days=200)).status_code == 200
    assert _post(body, start=TODAY + timedelta(days=366)).status_code == 422
    assert _post(body, start=TODAY - timedelta(days=1)).status_code == 422


def test_rice_uses_survey_price_and_national_market():
    d = _first_window("rice")
    o = next(x for x in _post([{"type": "paddy", "area_pyeong": 3000}], start=d, region="전남").json()["results"] if x["crop"] == "rice")
    assert o["price_basis"] == {"survey": 1.0} and o["market"]["code"] == "national" and o["no_market"]
    assert o["price_per_kg"] == CROPS["rice"].survey_price and o["farm_ratio"] is None


def test_markets_in_sido_and_no_market_region():
    d = _first_window("onion")
    o = next(x for x in _post([{"type": "open", "area_pyeong": 1000}], start=d, region="경기").json()["results"] if x["crop"] == "onion")
    assert len(o["market_compare"]) > 1 and sum(m["best"] for m in o["market_compare"]) == 1
    o = next(x for x in _post([{"type": "open", "area_pyeong": 1000}], start=d, region="세종").json()["results"] if x["crop"] == "onion")
    assert o["no_market"] and o["market"]["code"] == "national"


def test_ph_demotes_to_bottom():
    d = _first_window("potato")
    rs = _post([{"type": "open", "area_pyeong": 1000, "prev_crop": "상추"}], start=d).json()["results"]  # 상추 흙 pH 6.9 > 감자 최고 6.0 + 0.5
    pot = next(o for o in rs if o["crop"] == "potato")
    assert pot["demoted"] and pot["ph"]["kind"] == "lower"
    assert rs.index(pot) >= len([o for o in rs if not o["demoted"]])


def test_excluded_reasons():
    out = _post([{"type": "open", "area_pyeong": 1000}]).json()
    kinds = {e["crop"]: e["kind"] for e in out["excluded"]}
    assert kinds["apple"] == "perennial" and kinds["tomato"] == "land" and kinds["rice"] == "land"


# ── 다른 API ──
def test_planting_dates():
    d = client.post("/recommend/planting-dates", json={"crop": "tomato", "area_pyeong": 600}).json()
    assert len(d["points"]) == 53
    rates = [p["option"]["margin_rate"] for p in d["points"] if p["option"]]
    assert d["best"]["margin_rate"] >= max(rates) - 0.5
    assert 1 <= len(d["top"]) <= 3 and d["top"][0]["margin_rate"] >= d["top"][-1]["margin_rate"]
    assert client.post("/recommend/planting-dates", json={"crop": "tomato", "area_pyeong": 600, "land": "paddy"}).status_code == 422


def test_planting_dates_perennial_and_unknown():
    d = client.post("/recommend/planting-dates", json={"crop": "apple", "area_pyeong": 600}).json()
    assert d["note"] and d["points"] == [] and d["best"] is None
    assert client.post("/recommend/planting-dates", json={"crop": "durian", "area_pyeong": 600}).status_code == 404


def test_price_path_without_db_uses_normal():
    d = client.get("/recommend/crops/onion/prices").json()
    assert 40 <= len(d["points"]) <= 53
    assert all(p["lower"] <= p["price"] <= p["upper"] and p["basis"] == "normal" for p in d["points"])
    assert client.get("/recommend/crops/durian/prices").status_code == 404


def test_crop_info():
    d = client.get("/recommend/crops/watermelon").json()
    assert {c["land"] for c in d["croppings"]} == {"open", "house"}
    assert d["rda"]["source"] and d["rda"]["years"] and d["soil_ph"]["name"] == "수박"
    assert all(c["schedule_source"] and c["econ_source"] for c in d["croppings"])
    assert d["normal"]["price"] and len(d["normal"]["price"]) == 12
    a = client.get("/recommend/crops/apple").json()
    assert a["note"] and a["croppings"] == [] and a["harvest_months"]
    r = client.get("/recommend/crops/rice").json()
    assert r["price_source"] == "survey" and r["normal"] is None


# ── DB 예측을 쓸 때 (가짜 DB) ──
@pytest.fixture
def fake_db(monkeypatch):
    """onion: 모든 날 1000원(하한 800 · 상한 1300), 시장 110001 은 1.2배. 6월 이후 목표일은 출하철 밖"""
    def q(sql, params):
        if "price_forecast_daily" in sql:
            item = params[0]
            if item != "onion":
                return []
            rows = [(TODAY, TODAY + timedelta(days=k), 1000.0, 800.0, 1300.0, 1 if (TODAY + timedelta(days=k)).month in (6, 7, 8) else 0) for k in range(1, 366)]
            return rows if "off_season" in sql else [r[:5] for r in rows]
        if "market_factor" in sql:
            return [("110001", m, 1.2) for m in range(1, 13)] if params[0] == "onion" else []
        return []
    monkeypatch.setattr(crop_prices._Store, "_q", staticmethod(q))
    monkeypatch.setattr(crop_prices, "STORE", crop_prices._Store())


def test_forecast_price_market_factor_and_range(fake_db):
    crop = CROPS["onion"]
    c = crop.croppings[0]
    o = recommender.evaluate(crop, c, date(TODAY.year, 10, 15) if TODAY < date(TODAY.year, 10, 15) else _first_window("onion"), 302.5, TODAY)
    assert o is not None and o.basis.get("forecast", 0) > 0
    nat = o.at("national")
    seoul = o.at("110001")
    assert seoul.revenue == pytest.approx(nat.revenue * 1.2, rel=1e-6)
    w = next(x for x in nat.weeks if x.price.basis == "forecast")
    assert w.price.wholesale == pytest.approx(1000 * c.farm_ratio) and w.price.low < w.price.wholesale < w.price.high
    assert nat.revenue_low < nat.revenue < nat.revenue_high


def test_off_season_forecast_marks_reference(fake_db):
    crop = CROPS["onion"]
    c = crop.croppings[0]
    plant = next(TODAY + timedelta(days=k) for k in range(366) if c.in_window(TODAY + timedelta(days=k)))
    o = recommender.evaluate(crop, c, plant, 302.5, TODAY)
    if o.harvest_start.month in (6, 7, 8) and o.share(lambda w: w.price.basis == "forecast") > 0.5:
        assert o.reference == "baseline"
    path = client.get("/recommend/crops/onion/prices").json()
    assert path["forecast_base_date"] == TODAY.isoformat()
    assert {p["basis"] for p in path["points"]} == {"forecast"}
    assert any(p["off_season"] for p in path["points"]) and path["points"][0]["price"] == 1000


# ── 11-14 품종 작형: 양파 조생종은 조생(onion-3) 가격, 중만생종은 품목 전체 ──
def test_variety_cropping_uses_its_variety_price(monkeypatch):
    def q(sql, params):
        if "price_forecast_daily" in sql and params[0] == "onion":
            p = 2000.0 if params[1] == "onion-3" else 1000.0
            rows = [(TODAY, TODAY + timedelta(days=k), p, p * 0.8, p * 1.3, 0) for k in range(1, 366)]
            return rows if "off_season" in sql else [r[:5] for r in rows]
        return []
    monkeypatch.setattr(crop_prices._Store, "_q", staticmethod(q))
    monkeypatch.setattr(crop_prices, "STORE", crop_prices._Store())
    crop = CROPS["onion"]
    early, late = (next(c for c in crop.croppings if c.name.startswith(n)) for n in ("조생", "중만생"))
    assert early.price_variety == "onion-3" and early.normal_price and not late.price_variety
    d = TODAY + timedelta(days=10)
    assert crop_prices.farm_price(crop, early, d, TODAY).wholesale == pytest.approx(2000 * early.farm_ratio)
    assert crop_prices.farm_price(crop, late, d, TODAY).wholesale == pytest.approx(1000 * late.farm_ratio)
    assert early.harvest_from == (4, 1) and late.harvest_from == (6, 1)


# ── 11-16 예측 표에 일요일이 없음 → 그날 없으면 앞 3일 → 뒤 3일 안 가장 가까운 날 (평년으로 튀지 않게) ──
def test_missing_day_uses_nearest_forecast_day(monkeypatch):
    sat = date(2026, 11, 21)   # 토요일
    def q(sql, params):
        if "price_forecast_daily" in sql and params[0] == "onion":
            rows = [(TODAY, sat, 1234.0, 1000.0, 1500.0, 0), (TODAY, sat + timedelta(days=2), 1300.0, 1000.0, 1600.0, 0)]
            return rows if "off_season" in sql else [r[:5] for r in rows]
        return []
    monkeypatch.setattr(crop_prices._Store, "_q", staticmethod(q))
    monkeypatch.setattr(crop_prices, "STORE", crop_prices._Store())
    w = crop_prices.wholesale(CROPS["onion"], sat + timedelta(days=1), TODAY)   # 일요일
    assert w.basis == "forecast" and w.wholesale == 1234.0


# ── 11-16 점검: 고랭지 작형은 강원만 · 같은 순/같은 달 문구 ──
def test_highland_cropping_only_in_gangwon():
    hl = next(c for c in CROPS["napa_cabbage"].croppings if "고랭지" in c.name)
    assert hl.regions == ("강원",) and hl.allowed_in("강원") and not hl.allowed_in("경기") and hl.allowed_in(None)
    d = next(TODAY + timedelta(days=k) for k in range(366) if hl.in_window(TODAY + timedelta(days=k)))
    names = lambda region: [c.name for c in recommender.croppings_on(CROPS["napa_cabbage"], d, {"open": 600}, region)]
    assert hl.name in names("강원") and hl.name not in names("경기")
    nxt = recommender.next_window(CROPS["napa_cabbage"], d - timedelta(days=1), {"open": 600}, "경기")
    assert nxt is None or "고랭지" not in nxt[1].name


def test_window_text_collapses_same_ten_day_and_month():
    import dataclasses
    c = dataclasses.replace(CROPS["napa_cabbage"].croppings[0], plant_from=(6, 11), plant_to=(6, 20))
    assert recommender._window(c) == "6월 중순"
    c = dataclasses.replace(c, plant_to=(7, 5))
    assert recommender._window(c) == "6월 중순~7월 상순"
    from app.core.crop_catalog import _same_month_range
    assert _same_month_range("매년 10~10월에 수확해요") == "매년 10월에 수확해요"
    assert _same_month_range("매년 7~11월에 수확해요") == "매년 7~11월에 수확해요"
    assert "10~10월" not in (CROPS["sweet_persimmon"].perennial_note or "")


def test_market_factor_outliers_are_clipped_for_recommend(monkeypatch):
    """11-16: 계수 표 이상값(×6.1 등)이 '가장 비싼 시장'으로 뽑혀 순이익이 부풀던 것 → 0.67~1.5 로 자름"""
    monkeypatch.setattr(crop_prices.STORE, "factors", lambda item: {("380101", 4): 6.1, ("310101", 4): 0.2, ("110001", 4): 1.2})
    crop = CROPS["green_chili"]
    assert crop_prices.market_factor(crop, "380101", 4) == crop_prices.FACTOR_MAX == 1.5
    assert crop_prices.market_factor(crop, "310101", 4) == crop_prices.FACTOR_MIN == 0.67
    assert crop_prices.market_factor(crop, "110001", 4) == 1.2
    assert crop_prices.market_factor(crop, "national", 4) == 1.0


# ── 11-16 대량 시험 뒤 결정: 임대료는 재배 기간만큼 · 수확 철 값이 조사 가격의 2배 넘으면 '수량 참고' 표시 ──
def test_land_rent_is_prorated_by_growing_days():
    crop = CROPS["spinach"]
    c = next(x for x in crop.croppings if x.name == "가을재배")
    d = _first_window("spinach")
    o = recommender.evaluate(crop, c, d, 600, TODAY, recommender.Rent(land=365))   # 1년 365만원 = 하루 1만원
    days = (o.harvest_end - o.plant).days + 1
    assert o.land_rent == pytest.approx(10_000 * days)
    assert o.rent_days == days and o.land_rent_year == 3_650_000
    long = recommender.evaluate(CROPS["garlic"], CROPS["garlic"].croppings[0], _first_window("garlic"), 600, TODAY, recommender.Rent(land=365))
    assert long.land_rent <= 3_650_000  # 1년을 넘게 차지해도 1년치까지만


def test_peak_price_flag_when_price_far_above_survey(monkeypatch):
    crop = CROPS["spinach"]
    c = next(x for x in crop.croppings if x.name == "여름재배")
    d = next(TODAY + timedelta(days=k) for k in range(366) if c.in_window(TODAY + timedelta(days=k)))
    monkeypatch.setattr(crop_prices, "farm_price", lambda crop, c, day, today: crop_prices.Price(c.survey.price * 3, 1, 1, "normal"))
    o = recommender.evaluate(crop, c, d, 600, TODAY)
    assert o.peak_ratio == pytest.approx(3.0, rel=0.01)
    monkeypatch.setattr(crop_prices, "farm_price", lambda crop, c, day, today: crop_prices.Price(c.survey.price * 1.5, 1, 1, "normal"))
    assert recommender.evaluate(crop, c, d, 600, TODAY).peak_ratio is None


# ── 11-17 과수원: 다 자란 나무 기준 1년 소득 (조사 자료) ──
def test_orchard_gives_tree_crops_by_income():
    j = _post([{"type": "orchard", "area_pyeong": 1000, "land_rent": 100}], region="경북").json()
    assert j["results"] == [] and len(j["orchards"]) == 7
    o = j["orchards"]
    for t in ("main", None, "rare"):   # 11-18: 주산지 → 보통 → 거의 안 기름, 묶음 안에서는 소득 순
        ms = [x["margin"] for x in o if x["region_tier"] == t]
        assert ms == sorted(ms, reverse=True)
    assert [x["region_tier"] for x in o] == sorted((x["region_tier"] for x in o), key=lambda t: {"main": 0, None: 1, "rare": 2}[t])
    assert o[0]["region_tier"] == "main" and o[0]["crop"] in ("apple", "grape", "peach", "plum", "pear")
    a = next(x for x in o if x["crop"] == "apple")
    s = CROPS["apple"].survey
    a10 = 1000 / recommender.PYEONG_PER_10A
    assert a["revenue"] == round(s.revenue * a10) and a["land_rent"] == 1_000_000
    assert a["cost"] == round((s.cost - s.land_rent) * a10 + 1_000_000) and a["margin"] == a["revenue"] - a["cost"]
    m = next(x for x in o if x["crop"] == "mandarin")
    assert m["region_tier"] == "rare" and "거의 기르지 않는" in m["region_note"] and o[-1]["crop"] == "mandarin"   # 제주 밖 감귤은 안내 + 맨 아래


def test_orchard_in_jeju_puts_mandarin_first_and_other_lands_have_no_orchards():
    """11-18: 제주 과수원은 소득이 더 큰 포도·사과가 아니라 주산지인 감귤이 1위. 제주에서 거의 안 기르는 나무는 아래 + 안내"""
    o = _post([{"type": "orchard", "area_pyeong": 1000}], region="제주").json()["orchards"]
    assert o[0]["crop"] == "mandarin" and o[0]["region_tier"] == "main" and o[0]["region_share"] > 90 and "주산지" in o[0]["region_note"]
    assert all(x["region_tier"] == "rare" and x["region_note"] for x in o[1:])
    assert max(x["margin"] for x in o[1:]) > o[0]["margin"]   # 소득 숫자는 그대로 (순서만 바뀜)
    assert _post([{"type": "open", "area_pyeong": 1000}]).json()["orchards"] == []


def test_orchard_uses_best_market_in_sido(monkeypatch):
    """11-17: 과수원도 시·도 안 도매시장 계수(수확 달 평균)를 매출에 곱함 — 예전엔 어느 시·도든 같은 값"""
    from app.core.markets import markets_in_sido
    codes = [m.code for m in markets_in_sido("강원")]
    fac = {codes[0]: 1.2, codes[1]: 0.9}
    monkeypatch.setattr(crop_prices, "market_factor", lambda crop, market, month: fac.get(market, 1.0))
    o = {x["crop"]: x for x in _post([{"type": "orchard", "area_pyeong": 1000}], region="강원").json()["orchards"]}
    a10 = 1000 / recommender.PYEONG_PER_10A
    s = CROPS["apple"].survey
    assert o["apple"]["market"] == codes[0] and o["apple"]["market_factor"] == 1.2
    assert o["apple"]["revenue"] == round(s.revenue * a10 * 1.2)
    j = {x["crop"]: x for x in _post([{"type": "orchard", "area_pyeong": 1000}], region="제주").json()["orchards"]}
    assert j["apple"]["market"] == "national" and j["apple"]["revenue"] == round(s.revenue * a10)   # 제주는 공영도매시장이 없어 전국


# ── 11-17 입력 상한: 면적 30만 평 · 임대료 평당 2만원 · 농기계 1억 ──
def test_input_caps():
    ok = {"type": "open", "area_pyeong": 1000, "land_rent": 2000}
    assert _post([ok]).status_code == 200
    assert _post([{**ok, "area_pyeong": 300_001}]).status_code == 422
    r = _post([{**ok, "land_rent": 2001}])   # 1,000평 × 2만원 = 2,000만원까지
    assert r.status_code == 422 and "평당" in r.text
    assert _post([{**ok, "machine_rent": 10_001}]).status_code == 422


# ── 11-18 주산지: 그 시·도에서 실제로 많이 기르는 작물을 위로, 거의 안 기르는 작물을 아래로 (shared/crop_regions.json) ──
def test_crop_regions_table_is_real_shares():
    from app.core import crop_regions as cr
    from app.core.markets import SIDO
    assert cr.MAIN_PCT == 10 and cr.RARE_PCT == 1
    for code, row in cr.SHARE.items():
        assert code in CROPS and set(row) == set(SIDO)
        assert sum(row.values()) == pytest.approx(100, abs=1.0)        # 시·도 몫의 합 = 100% (반올림 오차)
    assert set(CROPS) - set(cr.SHARE) == {"rice", "soybean"}            # 경매 자료에 없는 작물만 빠짐
    assert cr.tier("mandarin", "제주") == "main" and cr.tier("mandarin", "경기") == "rare"
    assert cr.tier("apple", "경북") == "main" and cr.tier("apple", "제주") == "rare"
    assert cr.tier("onion", "제주") is None                             # 4.6% → 순위 그대로
    assert cr.tier("rice", "전남") is None and cr.tier("onion", "national") is None and cr.tier("onion", None) is None
    assert cr.note("onion", "양파", "제주") is None and "0.1% 미만" in cr.note("apple", "사과", "제주")


def test_region_tiers_order_field_crops():
    """노지: 주산지 → 보통 → 거의 안 기름. 소득 숫자는 시·도 순위 규칙과 상관없이 그대로"""
    from app.core import crop_regions as cr
    rank = {"main": 0, None: 1, "rare": 2}
    for region in ("제주", "강원", "전남", "경북", "경기"):
        for k in (0, 60, 150, 240):
            d = TODAY + timedelta(days=k)
            rs = _post([{"type": "open", "area_pyeong": 1000}], start=d, region=region).json()["results"]
            tiers = [o["region_tier"] for o in rs if not o["demoted"]]
            assert tiers == sorted(tiers, key=rank.get), (region, d, tiers)
            for o in rs:
                assert o["region_share"] == cr.share(o["crop"], region)
                assert (o["region_note"] is None) == (o["region_tier"] is None)
                assert abs(o["margin"] - (o["revenue"] - o["cost"])) <= 1


def test_all_rare_region_keeps_income_order_without_notes():
    """세종처럼 후보가 모두 '거의 안 기름'이면 내리지도 안내하지도 않음 (반입 산지 자료로 가릴 수 없음)"""
    j = _post([{"type": "orchard", "area_pyeong": 1000}], region="세종").json()["orchards"]
    assert all(x["region_tier"] is None and x["region_note"] is None for x in j)
    assert [x["margin"] for x in j] == sorted((x["margin"] for x in j), reverse=True)


def test_rare_crop_outside_top_is_explained_as_region():
    d = _first_window("onion", "open")
    j = _post([{"type": "open", "area_pyeong": 1000}], start=d, region="강원").json()
    rare = [o["crop"] for o in j["results"][recommender.TOP_N:] if o["region_tier"] == "rare" and not o["demoted"]]
    ex = {e["crop"]: e for e in j["excluded"]}
    for c in rare:
        assert ex[c]["kind"] == "region" and "거의 기르지 않는" in ex[c]["reason"]


def test_region_notice_explains_order_and_basis():
    """11-18: 결과 위 안내 — 규칙을 썼으면 순서·자료 기준, 가릴 수 없는 시·도면 그 사실, 그 밖에는 없음"""
    j = _post([{"type": "orchard", "area_pyeong": 1000}], region="제주").json()
    assert "제주가 주산지인" in j["region_notice"] and "도매시장" in j["region_notice"] and "소득 1위가 아닐 수" in j["region_notice"]
    j = _post([{"type": "orchard", "area_pyeong": 1000}], region="경북").json()
    assert "경북이 주산지인" in j["region_notice"]
    j = _post([{"type": "orchard", "area_pyeong": 1000}], region="세종").json()
    assert "세종산이 거의 들어오지 않는" in j["region_notice"] and "소득이 높은 순으로만" in j["region_notice"]
    d = _first_window("rice", "paddy")
    j = _post([{"type": "paddy", "area_pyeong": 3000}], start=d, region="전남").json()
    if all(o["crop"] in ("rice", "soybean") for o in j["results"]):
        assert j["region_notice"] is None                                # 주산지 자료가 없는 작물뿐


# ── 11-18 저녁: 후보가 적을 때 안내 · '수량 참고'에 반입량 사실 (소득 금액은 건드리지 않음) ──
def test_few_notice_only_when_one_or_two_candidates():
    kinds = set()
    for k in range(0, 365, 7):
        d = TODAY + timedelta(days=k)
        j = _post([{"type": "open", "area_pyeong": 1200}], start=d, region="경기").json()
        n = len(j["results"])
        assert (j["few_notice"] is not None) == (1 <= n <= recommender.FEW), (d, n)
        if j["few_notice"]:
            assert f"{n}개뿐" in j["few_notice"] and f"({d.month}/{d.day})" in j["few_notice"]
            kinds.add("곧 심을 수 있는 작물" in j["few_notice"])
    assert kinds   # 한 해 중 후보가 2개 이하인 주가 있음
    assert _post([{"type": "orchard", "area_pyeong": 1000}], region="경북").json()["few_notice"] is None


def test_month_share_table_and_peak_volume_note():
    from app.core import crop_regions as cr
    assert set(cr.MONTH_SHARE) == set(cr.SHARE)
    for row in cr.MONTH_SHARE.values():
        assert len(row) == 12 and sum(row) == pytest.approx(100, abs=1.0)
    assert cr.volume_share("spinach", [8]) < 2 < cr.volume_share("spinach", [12])     # 시금치는 8월에 거의 안 들어옴
    assert cr.volume_share("rice", [10]) is None
    seen = False
    for k in range(0, 365, 7):
        for o in _post([{"type": "open", "area_pyeong": 1200}], start=TODAY + timedelta(days=k), region="경기").json()["results"]:
            assert (o["peak_volume_note"] is not None) <= (o["peak_ratio"] is not None)   # '수량 참고'일 때만
            assert abs(o["margin"] - (o["revenue"] - o["cost"])) <= 1                      # 금액은 그대로
            if o["peak_volume_note"]:
                seen = True
                assert "1년 물량의" in o["peak_volume_note"] and o["crop_name"] in o["peak_volume_note"]
    assert seen

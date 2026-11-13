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
    margins = [o["margin"] for o in rs if not o["demoted"]]
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
    assert o["base_cost"] == pytest.approx(c.cost_per_10a, abs=1) and o["land_rent"] == 500_000
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

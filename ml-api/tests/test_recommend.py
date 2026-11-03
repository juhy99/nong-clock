from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
TODAY = date.today()


def test_crop_list():
    crops = client.get("/recommend/crops").json()
    codes = {c["code"] for c in crops}
    assert {"tomato", "green_onion", "rice", "apple"} <= codes
    apple = next(c for c in crops if c["code"] == "apple")
    assert apple["perennial"] and apple["land_type"] == "orchard"


def test_recommend_sorted_by_margin_and_consistent():
    body = {"lands": [{"type": "open", "area_pyeong": 1200}, {"type": "house", "area_pyeong": 600}], "start_date": TODAY.isoformat()}
    res = client.post("/recommend/crops", json=body)
    assert res.status_code == 200
    d = res.json()
    margins = [o["margin"] for o in d["results"]]
    assert margins == sorted(margins, reverse=True)
    for o in d["results"]:
        assert o["land_type"] in ("open", "house")
        assert abs(o["revenue"] - o["cost"] - o["margin"]) <= 1
        assert o["plant_date"] == TODAY.isoformat() and o["harvest_start"] < o["harvest_end"]
    # 결과에 없는 작물은 이유와 함께 unavailable 에
    shown = {o["crop"] for o in d["results"]} | {u["crop"] for u in d["unavailable"]}
    assert "rice" not in shown  # 논을 고르지 않음


def test_recommend_start_date_must_be_within_30_days():
    body = {"lands": [{"type": "open", "area_pyeong": 100}], "start_date": (TODAY + timedelta(days=31)).isoformat()}
    assert client.post("/recommend/crops", json=body).status_code == 422
    body["start_date"] = (TODAY - timedelta(days=1)).isoformat()
    assert client.post("/recommend/crops", json=body).status_code == 422


def test_planting_dates():
    d = client.post("/recommend/planting-dates", json={"crop": "tomato", "area_pyeong": 600}).json()
    assert len(d["points"]) == 53
    best = d["best"]
    rates = [p["option"]["margin_rate"] for p in d["points"] if p["option"]]
    assert best["margin_rate"] >= max(rates) - 0.5
    assert 1 <= len(d["top"]) <= 3 and d["top"][0]["margin_rate"] >= d["top"][-1]["margin_rate"]


def test_planting_dates_perennial_and_unknown():
    d = client.post("/recommend/planting-dates", json={"crop": "apple", "area_pyeong": 600}).json()
    assert d["note"] and d["points"] == [] and d["best"] is None
    assert client.post("/recommend/planting-dates", json={"crop": "durian", "area_pyeong": 600}).status_code == 404


def test_price_path():
    d = client.get("/recommend/crops/tomato/prices").json()
    assert len(d["points"]) == 57 and d["points"][0]["date"] == TODAY.isoformat()
    assert all(p["lower"] <= p["price"] <= p["upper"] for p in d["points"])
    assert client.get("/recommend/crops/apple/prices").json()["points"] == []
    assert client.get("/recommend/crops/durian/prices").status_code == 404


def test_recommend_market_rent_and_scenarios():
    body = {"lands": [{"type": "house", "area_pyeong": 600, "land_rent": 80, "machine_rent": 30}], "start_date": TODAY.isoformat(), "region": "전남"}
    d = client.post("/recommend/crops", json=body).json()
    assert d["region"] == "전남" and d["market"]["code"] == "240004"  # 전남 → 가장 가까운 광주서부
    for o in d["results"]:
        assert o["land_rent"] == 800_000 and o["machine_rent"] == 300_000
        assert abs(o["base_cost"] + o["land_rent"] + o["machine_rent"] - o["cost"]) <= 1
        assert abs(o["revenue"] - o["cost"] - o["margin"]) <= 1
        assert o["margin_low"] < o["margin"] < o["margin_high"]
        assert o["harvest_start"] < o["harvest_end"] <= o["storage_end"]
        assert abs(sum(m["t"] for m in o["shipments"]) - o["sellable_t"]) < 0.05
        assert abs(sum(m["revenue"] for m in o["shipments"]) - o["revenue"]) <= len(o["shipments"])
        codes = [m["code"] for m in o["market_compare"]]
        assert codes[0] == "240004" and "110001" in codes and codes[-1] == "national"
        here = next(m for m in o["market_compare"] if m["code"] == o["market"]["code"])
        assert here["margin"] == o["margin"]


def test_recommend_market_choice_changes_revenue_only():
    base = {"lands": [{"type": "house", "area_pyeong": 600}], "start_date": TODAY.isoformat(), "region": "충남"}
    a = client.post("/recommend/crops", json={**base, "market": "national"}).json()["results"]
    b = client.post("/recommend/crops", json={**base, "market": "110001"}).json()["results"]
    by = {o["crop"]: o for o in b}
    for o in a:
        x = by[o["crop"]]
        assert x["cost"] == o["cost"] and x["market"]["name"] == "서울가락"
        assert abs(x["revenue"] - o["revenue"] * x["factor"]) <= o["revenue"] * 1e-4  # factor 는 소수 4자리로 반올림돼 나옴


def test_crop_calendar_sources_and_realistic_harvest():
    from app.core.crop_calendar import CROPS

    assert CROPS["tomato"].croppings[0].source == "rda" and CROPS["onion"].croppings[0].source == "est"
    for code in ("onion", "garlic", "potato", "rice"):  # 한 번에 거두는 작물
        assert all(c.harvest_days <= 30 and not c.multi_harvest for c in CROPS[code].croppings)
    assert CROPS["tomato"].croppings[0].multi_harvest


def test_planting_dates_with_market_and_rent():
    d = client.post("/recommend/planting-dates", json={"crop": "tomato", "area_pyeong": 600, "region": "경남", "land_rent": 100}).json()
    o = d["best"]
    assert o["market"]["code"] in {"380101", "380303", "380401"} and o["land_rent"] == 1_000_000


def test_market_factor_matches_frontend():
    from app.core.markets import market_factor

    # frontend/src/mocks/market.js marketFactor 와 같은 값
    assert abs(market_factor("tomato", "110001") - 1.004218862624839) < 1e-12
    assert abs(market_factor("cucumber", "240004") - 1.0530387503094971) < 1e-12

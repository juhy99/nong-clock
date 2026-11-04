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


def test_recommend_sido_markets_rent_and_scenarios():
    body = {"lands": [{"type": "house", "area_pyeong": 600, "land_rent": 80, "machine_rent": 30}], "start_date": TODAY.isoformat(), "region": "경기"}
    d = client.post("/recommend/crops", json=body).json()
    assert d["region"] == "경기" and not d["no_market"]
    assert {m["name"] for m in d["markets"]} == {"수원", "안양", "안산", "구리"}  # 경기 안 시장끼리만
    for o in d["results"]:
        assert o["land_rent"] == 800_000 and o["machine_rent"] == 300_000
        assert abs(o["base_cost"] + o["land_rent"] + o["machine_rent"] - o["cost"]) <= 1
        assert abs(o["revenue"] - o["cost"] - o["margin"]) <= 1
        assert o["margin_low"] < o["margin"] < o["margin_high"]
        assert o["harvest_start"] < o["harvest_end"] <= o["storage_end"]
        assert abs(sum(m["t"] for m in o["shipments"]) - o["sellable_t"]) < 0.05
        assert abs(sum(m["revenue"] for m in o["shipments"]) - o["revenue"]) <= len(o["shipments"])
        cmp = o["market_compare"]
        assert {m["name"] for m in cmp} == {"수원", "안양", "안산", "구리"}
        best = [m for m in cmp if m["best"]]
        assert len(best) == 1 and best[0]["code"] == o["market"]["code"] and best[0]["margin"] == max(m["margin"] for m in cmp) == o["margin"]


def test_recommend_one_market_and_no_market():
    base = {"lands": [{"type": "house", "area_pyeong": 600}], "start_date": TODAY.isoformat()}
    one = client.post("/recommend/crops", json={**base, "region": "충남"}).json()
    assert [m["name"] for m in one["markets"]] == ["천안"]
    assert all(len(o["market_compare"]) == 1 and o["market"]["name"] == "천안" for o in one["results"])
    for sido in ("제주", "세종"):  # 공영 도매시장이 없음 → 다른 지역을 섞지 않고 전국 평균
        d = client.post("/recommend/crops", json={**base, "region": sido}).json()
        assert d["no_market"] and [m["code"] for m in d["markets"]] == ["national"]
        assert all(o["market"]["code"] == "national" and o["factor"] == 1 and o["no_market"] for o in d["results"])


def test_recommend_ph_demotes_to_bottom():
    from datetime import date

    from app.services import recommender

    # 봄(3/10) 노지: 감자(pH 5.0~6.0)는 기존 작물 상추(6.6~7.2 → 흙 약 6.9)면 0.9 높아서 맨 아래
    start = date(TODAY.year + 1, 3, 10)
    ok, _ = recommender.recommend_crops({"open": 1200}, {}, start, TODAY, "경기", prevs={"open": "상추"})
    codes = [o.crop.code for o in ok]
    assert "potato" in codes and codes[-1] == "potato"
    potato = ok[-1]
    assert potato.demoted and potato.soil_ph == 6.9 and potato.ph[0] == "lower" and potato.ph[2] == 0.9
    rest = [o for o in ok if not o.demoted]
    assert [o.margin for o in rest] == sorted((o.margin for o in rest), reverse=True)
    # 기존 작물이 없으면 pH 비교 안 함
    ok2, _ = recommender.recommend_crops({"open": 1200}, {}, start, TODAY, "경기")
    assert all(o.ph is None and not o.demoted for o in ok2)
    # 0.5 보다 덜 높으면(오이 최고 6.8, 흙 6.9) 내리지 않음
    from app.core.soil_ph import ph_check

    assert ph_check("cucumber", 6.9)[0] == "near" and ph_check("onion", 5.5)[0] == "raise"


def test_recommend_excluded_reasons():
    body = {"lands": [{"type": "open", "area_pyeong": 1200}, {"type": "house", "area_pyeong": 600}], "start_date": TODAY.isoformat(), "region": "경기"}
    d = client.post("/recommend/crops", json=body).json()
    ex = {e["crop"]: e for e in d["excluded"]}
    top = [o["crop"] for o in d["results"][:3]]
    assert not set(top) & set(ex)  # 상위 3개는 excluded 에 없음
    assert ex["apple"]["kind"] == "perennial" and "다년생" in ex["apple"]["reason"]
    assert ex["rice"]["kind"] == "land" and "논 토지에서만" in ex["rice"]["reason"] and "노지·시설" in ex["rice"]["reason"]
    assert ex["potato"]["kind"] == "season" and "심는 시기가 아니에요" in ex["potato"]["reason"]
    for o in d["results"][3:]:
        assert ex[o["crop"]]["kind"] in ("low", "ph")


def test_crop_info():
    d = client.get("/recommend/crops/cucumber").json()
    assert d["crop"]["land_type"] == "house" and d["rda"]["row"] == "시설오이"
    assert d["soil_ph"]["min"] == 5.5 and d["soil_ph"]["max"] == 6.8
    assert [c["name"] for c in d["croppings"]] == ["촉성재배", "반촉성재배", "억제재배"]
    assert d["croppings"][0]["source"] == "rda" and d["croppings"][1]["source"] == "est"
    apple = client.get("/recommend/crops/apple").json()
    assert apple["note"] and apple["croppings"] == []
    assert client.get("/recommend/crops/durian").status_code == 404


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

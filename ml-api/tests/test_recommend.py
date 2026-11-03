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

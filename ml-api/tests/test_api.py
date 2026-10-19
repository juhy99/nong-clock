import pytest
from fastapi.testclient import TestClient

from app.core.catalog import REGIONS
from app.main import app

client = TestClient(app)


def test_health():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_items_and_regions():
    items = client.get("/items").json()
    assert len(items) == 16
    assert any(i["code"] == "napa_cabbage" for i in items)
    assert all(i["unit"] == "kg" and i["emoji"] for i in items)
    # 기본은 전국만
    assert client.get("/regions").json() == [{"code": "national", "name": "전국"}]


def test_horizons():
    assert client.get("/horizons").json() == [
        {"days": 7, "label": "1주"},
        {"days": 14, "label": "2주"},
        {"days": 30, "label": "1개월"},
    ]


def test_regional_forecast_when_enabled(monkeypatch):
    monkeypatch.setitem(REGIONS, "gyeonggi", "경기")
    assert len(client.get("/regions").json()) == 2
    res = client.post("/predict", json={"item": "napa_cabbage", "region": "gyeonggi", "horizon": 7})
    assert res.status_code == 200 and res.json()["region"] == "gyeonggi"


def test_region_defaults_to_national():
    res = client.post("/predict", json={"item": "napa_cabbage", "horizon": 7})
    assert res.status_code == 200
    assert res.json()["region"] == "national"
    assert client.get("/predict/top-movers").status_code == 200


@pytest.mark.parametrize("horizon", [1, 7, 10, 14, 23, 30])
def test_predict_shape(horizon):
    res = client.post("/predict", json={"item": "napa_cabbage", "horizon": horizon})
    assert res.status_code == 200
    body = res.json()
    assert len(body["forecast"]) == horizon
    assert body["predicted_price"] == body["forecast"][-1]["price"]
    assert all(p["lower"] <= p["price"] <= p["upper"] for p in body["forecast"])
    assert 0 <= body["confidence"] <= 100


def test_predict_is_deterministic():
    req = {"item": "napa_cabbage", "horizon": 14}
    assert client.post("/predict", json=req).json() == client.post("/predict", json=req).json()


@pytest.mark.parametrize(
    "req, status",
    [
        ({"item": "banana", "horizon": 7}, 404),
        ({"item": "napa_cabbage", "region": "seoul", "horizon": 7}, 404),
        ({"item": "napa_cabbage", "horizon": 0}, 422),
        ({"item": "napa_cabbage", "horizon": 31}, 422),
        ({"item": "napa_cabbage", "region": "gyeonggi", "horizon": 7}, 404),  # 지역별 예측 꺼짐
    ],
)
def test_predict_invalid(req, status):
    assert client.post("/predict", json=req).status_code == status


@pytest.mark.parametrize("horizon", [1, 7, 10, 30])
def test_top_movers_horizon_query(horizon):
    # 쿼리 파라미터는 문자열로 들어온다 ("7") — 회귀 테스트
    assert client.get(f"/predict/top-movers?horizon={horizon}&limit=2").status_code == 200


@pytest.mark.parametrize("horizon", [0, 31])
def test_top_movers_invalid_horizon(horizon):
    assert client.get(f"/predict/top-movers?horizon={horizon}").status_code == 422


def test_top_movers_sorted():
    movers = client.get("/predict/top-movers", params={"limit": 4}).json()
    assert len(movers) == 4
    changes = [abs(m["change_pct"]) for m in movers]
    assert changes == sorted(changes, reverse=True)

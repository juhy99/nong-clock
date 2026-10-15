import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_items_and_regions():
    assert any(i["code"] == "cabbage" for i in client.get("/items").json())
    assert any(r["code"] == "gyeonggi" for r in client.get("/regions").json())


@pytest.mark.parametrize("horizon", [7, 14, 30])
def test_predict_shape(horizon):
    res = client.post("/predict", json={"item": "lettuce", "region": "gyeonggi", "horizon": horizon})
    assert res.status_code == 200
    body = res.json()
    assert len(body["forecast"]) == horizon
    assert body["predicted_price"] == body["forecast"][-1]["price"]
    assert all(p["lower"] <= p["price"] <= p["upper"] for p in body["forecast"])
    assert 0 <= body["confidence"] <= 100


def test_predict_is_deterministic():
    req = {"item": "cabbage", "region": "gangwon", "horizon": 14}
    assert client.post("/predict", json=req).json() == client.post("/predict", json=req).json()


@pytest.mark.parametrize(
    "req, status",
    [
        ({"item": "banana", "region": "gyeonggi", "horizon": 7}, 404),
        ({"item": "cabbage", "region": "seoul", "horizon": 7}, 404),
        ({"item": "cabbage", "region": "gyeonggi", "horizon": 10}, 422),
    ],
)
def test_predict_invalid(req, status):
    assert client.post("/predict", json=req).status_code == status


def test_top_movers_sorted():
    movers = client.get("/predict/top-movers", params={"limit": 4}).json()
    assert len(movers) == 4
    changes = [abs(m["change_pct"]) for m in movers]
    assert changes == sorted(changes, reverse=True)

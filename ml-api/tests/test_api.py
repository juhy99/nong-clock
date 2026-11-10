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
    assert len(items) == 50  # 예측 품목 50개 (shared/items50.json, 11-11)
    assert items[0]["code"] == "onion"  # 물량 순위 1위
    codes = {i["code"] for i in items}
    # 기존 16개 영어 코드는 그대로 (양송이 button_mushroom 은 50품목에 없어 빠짐)
    assert {"potato", "onion", "carrot", "apple", "watermelon", "napa_cabbage", "radish", "tomato", "cabbage", "sweet_potato",
            "pear", "king_oyster_mushroom", "green_onion", "mandarin", "enoki_mushroom"} <= codes and "button_mushroom" not in codes
    assert all(i["unit"] == "kg" and i["emoji"] and len(i["code4"]) == 4 and i["category"] for i in items)
    assert len({i["code4"] for i in items}) == 50 and len(codes) == 50
    # 기본은 전국만
    assert client.get("/regions").json() == [{"code": "national", "name": "전국"}]


def test_horizons():
    assert client.get("/horizons").json() == [
        {"days": 7, "label": "1주"},
        {"days": 14, "label": "2주"},
        {"days": 30, "label": "1개월"},
        {"days": 90, "label": "3개월"},
        {"days": 180, "label": "6개월"},
        {"days": 365, "label": "1년"},
    ]


def test_markets():
    ms = client.get("/markets").json()
    assert len(ms) == 32 and ms[0]["code"] == "110001" and ms[0]["name"] == "서울가락"
    assert {m["name"] for m in ms if m["sido"] == "경기"} == {"수원", "안양", "안산", "구리"}


def test_predict_market_and_one_year():
    res = client.post("/predict", json={"item": "tomato", "market": "110001", "horizon": 365})
    assert res.status_code == 200
    b = res.json()
    assert b["market"] == "110001" and b["market_name"] == "서울가락" and b["code4"] == "0803"
    assert len(b["forecast"]) == 365
    # 장기일수록 범위가 넓다
    w = lambda p: (p["upper"] - p["lower"]) / p["price"]  # noqa: E731
    assert w(b["forecast"][364]) > w(b["forecast"][89]) > w(b["forecast"][6])
    nat = client.post("/predict", json={"item": "tomato", "horizon": 30}).json()
    assert nat["market"] == "national" and nat["base_price"] == 3810
    assert client.post("/predict", json={"item": "tomato", "market": "999999", "horizon": 7}).status_code == 404


def test_regional_forecast_when_enabled(monkeypatch):
    monkeypatch.setitem(REGIONS, "gyeonggi", "경기")
    assert len(client.get("/regions").json()) == 2
    res = client.post("/predict", json={"item": "napa_cabbage", "region": "gyeonggi", "horizon": 7})
    assert res.status_code == 200 and res.json()["region"] == "gyeonggi"


def test_predict_only_50_items():
    # 107개 중 50개 밖 품목(석류)은 예측하지 않음
    assert client.post("/predict", json={"item": "pomegranate", "horizon": 7}).status_code == 404


def test_predict_base_date_history_and_last_year():
    from datetime import date, timedelta

    today = date.today()
    base = today - timedelta(days=30)
    b = client.post("/predict", json={"item": "napa_cabbage", "horizon": 28, "base_date": base.isoformat(), "history_days": 56, "last_year": True}).json()
    assert b["base_date"] == base.isoformat()
    assert len(b["history"]) == 57 and b["history"][0]["date"] == (base - timedelta(days=56)).isoformat() and b["history"][-1]["date"] == base.isoformat()
    assert len(b["forecast"]) == 28 and b["forecast"][0]["date"] == (base + timedelta(days=1)).isoformat()
    # 작년 같은 시기: history 첫날 ~ forecast 마지막 날, 52주 전 같은 요일
    ly = b["last_year"]
    assert len(ly) == 56 + 28 + 1
    assert ly[0]["date"] == (base - timedelta(days=56 + 364)).isoformat() and ly[-1]["date"] == (base + timedelta(days=28 - 364)).isoformat()
    assert all(p["price"] > 0 for p in ly)
    # 기본은 오늘 · 14일 · 작년 없음
    d = client.post("/predict", json={"item": "napa_cabbage", "horizon": 7}).json()
    assert d["base_date"] == today.isoformat() and len(d["history"]) == 15 and d["last_year"] == []
    # 기준일은 오늘 ~ 1년 전, history_days 1~400
    assert client.post("/predict", json={"item": "napa_cabbage", "horizon": 7, "base_date": (today + timedelta(days=1)).isoformat()}).status_code == 422
    assert client.post("/predict", json={"item": "napa_cabbage", "horizon": 7, "base_date": (today - timedelta(days=366)).isoformat()}).status_code == 422
    assert client.post("/predict", json={"item": "napa_cabbage", "horizon": 7, "history_days": 401}).status_code == 422


def test_region_defaults_to_national():
    res = client.post("/predict", json={"item": "napa_cabbage", "horizon": 7})
    assert res.status_code == 200
    assert res.json()["region"] == "national"
    assert client.get("/predict/top-movers").status_code == 200


@pytest.mark.parametrize("horizon", [1, 7, 10, 14, 23, 30, 90, 365])
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
        ({"item": "durian", "horizon": 7}, 404),
        ({"item": "napa_cabbage", "region": "seoul", "horizon": 7}, 404),
        ({"item": "napa_cabbage", "horizon": 0}, 422),
        ({"item": "napa_cabbage", "horizon": 366}, 422),
        ({"item": "napa_cabbage", "region": "gyeonggi", "horizon": 7}, 404),  # 지역별 예측 꺼짐
    ],
)
def test_predict_invalid(req, status):
    assert client.post("/predict", json=req).status_code == status


@pytest.mark.parametrize("horizon", [1, 7, 10, 30, 365])
def test_top_movers_horizon_query(horizon):
    # 쿼리 파라미터는 문자열로 들어온다 ("7") — 회귀 테스트
    assert client.get(f"/predict/top-movers?horizon={horizon}&limit=2").status_code == 200


@pytest.mark.parametrize("horizon", [0, 366])
def test_top_movers_invalid_horizon(horizon):
    assert client.get(f"/predict/top-movers?horizon={horizon}").status_code == 422


def test_top_movers_sorted():
    movers = client.get("/predict/top-movers", params={"limit": 4}).json()
    assert len(movers) == 4
    changes = [abs(m["change_pct"]) for m in movers]
    assert changes == sorted(changes, reverse=True)


def test_predict_band_and_confidence_follow_model_accuracy():
    from app.core import accuracy

    # 배추 1주: 검증 WAPE 13.1% → 띠 = 예측 ± 13.1%, 신뢰도 = 100 − 13.1
    b = client.post("/predict", json={"item": "napa_cabbage", "horizon": 7}).json()
    last = b["forecast"][-1]
    assert abs((last["upper"] - last["price"]) / last["price"] - 0.131) < 0.002
    assert b["error_pct"] == 13.1 and b["confidence"] == 87 and b["reference"] is None
    # 6개월보다 먼 날은 6개월 오차보다 넓고 참고용
    far = client.post("/predict", json={"item": "napa_cabbage", "horizon": 365}).json()
    assert far["reference"] == "far" and far["error_pct"] > accuracy.ACC["items"]["napa_cabbage"]["wape"]["180"]
    # 기준선보다 나쁜 품목·기간은 참고용
    assert client.post("/predict", json={"item": "cabbage", "horizon": 30}).json()["reference"] == "baseline"
    assert client.post("/predict", json={"item": "cabbage", "horizon": 14}).json()["reference"] is None
    assert client.post("/predict", json={"item": "carrot", "horizon": 90}).json()["reference"] == "baseline"
    assert client.post("/predict", json={"item": "radish", "horizon": 30}).json()["reference"] == "baseline"


def test_accuracy_table():
    from app.core import accuracy

    assert len(accuracy.ACC["items"]) == 107
    assert accuracy.AVERAGE == {7: 17.69, 14: 20.45, 30: 22.93, 90: 24.66, 180: 26.83}
    ref = {c: v["reference_only"] for c, v in accuracy.ACC["items"].items() if v["reference_only"]}
    assert ref == {"cabbage": [30, 90, 180], "carrot": [90, 180], "radish": [30], "pomegranate": [180]}
    # 기간 사이는 이어짐
    w = accuracy.ACC["items"]["tomato"]["wape"]
    assert abs(accuracy.error_pct("tomato", 22) - (w["14"] + (w["30"] - w["14"]) * 8 / 16)) < 1e-9

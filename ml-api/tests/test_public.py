"""로그인 없이 보는 미리보기 주소 (11-17): 정해진 조건으로만 답한다 — 본 기능(/predict · /recommend)은 서버(nginx)가 회원만 통과시킴"""
from datetime import date

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_preview_predict_fixed_shape():
    r = client.get("/public/predict", params={"item": "apple"})
    assert r.status_code == 200
    d = r.json()
    assert d["item"] == "apple" and d["market"] == "national" and len(d["forecast"]) <= 28
    same = client.post("/predict", json={"item": "apple", "horizon": 28, "history_days": 49}).json()
    assert d["forecast"] == same["forecast"] and d["history"] == same["history"]   # 본 기능의 전국 4주와 같은 값
    assert client.get("/public/predict", params={"item": "apple", "horizon": 7}).status_code == 200


def test_preview_predict_refuses_member_options():
    assert client.get("/public/predict", params={"item": "apple", "horizon": 365}).status_code == 422   # 7 · 28 만
    assert client.get("/public/predict", params={"item": "apple", "horizon": 14}).status_code == 422
    assert client.get("/public/predict", params={"item": "없는품목"}).status_code == 404
    assert client.get("/public/predict").status_code == 422
    # 시장 · 품종 · 기준일을 붙여도 무시하고 전국 · 오늘 기준으로만
    d = client.get("/public/predict", params={"item": "apple", "market": "110001", "variety": "apple-1", "base_date": "2026-01-01", "history_days": 300}).json()
    assert d["market"] == "national" and d["base_date"] == date.today().isoformat() and len(d["history"]) <= 50
    assert client.post("/public/predict", json={"item": "apple", "horizon": 365}).status_code == 405


def test_preview_recommend_top3_only():
    r = client.get("/public/recommend", params={"region": "경기", "type": "open"})
    assert r.status_code == 200
    d = r.json()
    assert len(d["results"]) <= 3 and d["excluded"] == [] and d["unavailable"] == [] and len(d["orchards"]) <= 3
    assert d["start_date"] == date.today().isoformat() and d["region"] == "경기"
    full = client.post("/recommend/crops", json={"region": "경기", "lands": [{"type": "open", "area_pyeong": 1200}], "start_date": date.today().isoformat()}).json()
    assert [x["crop"] for x in d["results"]] == [x["crop"] for x in full["results"][:3]]
    assert all(x["area_pyeong"] == 1200 for x in d["results"])
    assert client.get("/public/recommend").status_code == 200   # 기본 경기 · 노지
    assert client.get("/public/recommend", params={"region": "화성"}).status_code == 422
    assert client.get("/public/recommend", params={"type": "roof"}).status_code == 422

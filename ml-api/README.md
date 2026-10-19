# Machine Learning API
- 파이썬 머신러닝 모델을 웹 서비스와 연동하기 위한 FastAPI 서버 폴더입니다.
- 현재는 **더미 예측기**가 응답합니다. 응답 형식은 실제 모델이 붙어도 그대로 유지하므로, Spring·프론트는 지금 형식 기준으로 개발하면 됩니다.

## 실행

```bash
cd ml-api
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

- API 문서(Swagger): http://localhost:8000/docs
- Docker: 루트에서 `docker compose up --build ml-api`
- 테스트: `pytest`

## 엔드포인트

| 메서드 | 경로 | 용도 | 화면 |
|---|---|---|---|
| GET | `/health` | 상태 확인 | - |
| GET | `/items` | 품목 코드 목록 (이름·분류·이모지 포함) | 품종 선택, 시세 카드 |
| GET | `/regions` | 지역 목록 (현재 전국만) | 지역 선택 (1개면 숨김) |
| GET | `/horizons` | 예측 기간 목록 (1주/2주/1개월) | 기간 버튼 |
| POST | `/predict` | 품목·지역·기간별 예측 | AI 가격예측 |
| GET | `/predict/top-movers?horizon=7&limit=4` | 변동률 절댓값 큰 순 품목 | 홈 · AI 추천 급등락 예상 품목 |

### POST /predict 예시

```json
// 요청
{ "item": "napa_cabbage", "horizon": 14 }

// 응답 (일부) — 가격은 모두 원/kg
{
  "item": "napa_cabbage", "item_name": "배추", "unit": "kg", "region": "national",
  "horizon": 14, "base_date": "2026-10-19", "base_price": 800,
  "history":  [{ "date": "2026-10-05", "price": 689 }, ...],
  "forecast": [{ "date": "2026-10-20", "price": 790, "lower": 766, "upper": 814 }, ...],
  "predicted_price": 722, "change_pct": -9.8, "confidence": 79,
  "alerts": [{ "start": "2026-10-26", "end": "2026-10-28", "reason": "...",
               "mape_normal": 6.2, "mape_anomaly": 19.8 }],
  "model_version": "dummy-0.1"
}
```

- 가격 단위는 전 품목 **원/kg** (`unit` 은 항상 `"kg"`)
- `region` 은 생략 가능하며 기본값은 `national`(전국). 지역별 예측은 `ENABLE_REGIONAL_FORECAST=true` 로 켬
- `horizon`: 7 / 14 / 30 중 하나 (그 외 422). 목록은 `GET /horizons`
- 없는 품목·지역 코드: 404

## 구조

```
app/
  main.py               # FastAPI 앱, CORS, 라우터 등록
  core/catalog.py       # 품목·지역 코드표 (팀 공통 코드)
  core/config.py        # 환경변수 (MODEL_VERSION, CORS_ORIGINS)
  schemas/              # 요청·응답 Pydantic 모델 = API 명세
  routers/              # 엔드포인트
  services/predictor.py # 예측기 (DummyPredictor → 실제 모델로 교체할 곳)
tests/
```

## 실제 모델로 교체하기
`services/predictor.py`의 `Predictor` 프로토콜을 구현하는 클래스를 만들고 `get_predictor()`가 그 클래스를 반환하게 바꾸면 됩니다. 라우터와 응답 형식은 수정할 필요가 없습니다.

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
| GET | `/items` | 품목 107개 (이름·`code4` 공영 품목코드·공영 부류·이모지) | 품목 선택 상자, 시세 카드 |
| GET | `/markets` | 공영 도매시장 32곳 | AI 가격예측 › 도매시장 |
| GET | `/regions` | (예전 방식) 지역 목록 — 전국만 | - |
| GET | `/horizons` | 예측 기간 빠른 선택 (1주~1년) | 기간 버튼 |
| POST | `/predict` | 품목·도매시장별 예측, 최대 365일 일별 | AI 가격예측 |
| GET | `/predict/top-movers?horizon=7&limit=4` | 변동률 절댓값 큰 순 품목 | 홈 · AI 추천 급등락 예상 품목 |
| GET | `/recommend/crops` | 작물 추천용 작물 목록 | 작물 추천 |
| POST | `/recommend/crops` | 토지 위치(시·도)·토지별 평수·임대료·기존 작물·시작 날짜 → 순이익 높은 작물 순(pH 맨 아래) + 빠진 이유 `excluded` | 작물 추천 › 내 땅으로, 작물 정보 |
| GET | `/recommend/crops/{code}` | 작물 정보 (작형·수량·경영비·pH) | 작물 추천 › 작물 정보 |
| POST | `/recommend/planting-dates` | 작물 → 1년 중 가장 좋은 심는 날 (화면에서는 안 씀) | - |
| GET | `/recommend/crops/{code}/prices` | 13개월 예상 도매가 | 작물 추천 › 상세 그래프 |

**목록 파일:** 품목 107개(`shared/items.json`), 도매시장 32곳(`shared/markets.json`), 작물별 흙 pH(`shared/soil_ph.json`)는 저장소 맨 위 `shared/` 에 있고 화면과 같이 읽어요 (`app/core/shared.py`). 그래서 도커는 저장소 맨 위에서 빌드해요(`docker compose` 가 알아서 함, 직접 할 때는 `docker build -f ml-api/Dockerfile .`).

작물 추천의 작물 달력·수량·경영비·월별 예상가는 `app/core/crop_calendar.py`(농진청 2024 농산물소득조사 + 추정값, `source` 로 구분), 시장 계수는 `app/core/markets.py`, pH 비교는 `app/core/soil_ph.py` 에 있어요. 자세한 형식은 `docs/06_api_spec.md` 1-2 · 1-3 · 1-4 · 1-6.

### POST /predict 예시

```json
// 요청 — market 생략하면 전국 평균, horizon 1~365
{ "item": "napa_cabbage", "market": "110001", "horizon": 14 }

// 응답 (일부) — 가격은 모두 원/kg
{
  "item": "napa_cabbage", "item_name": "배추", "code4": "1001", "unit": "kg",
  "market": "110001", "market_name": "서울가락", "region": "national",
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
- `market` 은 도매시장 코드(`GET /markets`), 생략하면 `national`(전국 평균). 지금 시장별 값 = 전국 예측 × 시장 계수 (`app/core/markets.py`)
- `region` 은 예전 방식(전국만), 안 보내도 됨
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

# 농업 뉴스 수집기

NAVER API HUB 뉴스 검색으로 기사를 받아 **농업 기사만 골라 품목·분류 태그를 붙여** `data/news.json` 에 쌓습니다. (명세 `docs/06_api_spec.md` 2-14)
파이썬 3.9 이상, 설치할 라이브러리 없음 (표준 라이브러리만).

## 실행

```powershell
cd collector\news
copy .env.example .env      # 처음 한 번: NAVER API HUB Client ID · Secret 입력 (커밋 금지)
python collect_news.py           # 한 번 수집
python collect_news.py --loop    # 1시간마다 계속 (Ctrl+C 로 멈춤)
python collect_news.py --relabel # 규칙을 바꾼 뒤 저장된 기사에 다시 적용 (네이버 호출 없음)
python -m unittest -v            # 검사
```

```
✓ 2026-10-22T18:00  검색어 27개 · 받은 기사 2416 · 새로 저장 312 · 거름 1650
```

## 하는 일

| 단계 | 내용 |
|---|---|
| 검색 | 기본("농산물 가격·수급") + 품목 16개 + 품목 밖 작물 9개 = 27개, 최신순 100건씩 |
| 새 기사만 | 지난 수집 시각(− 2시간 여유) 이후 기사만. 처음엔 검색어마다 100건 |
| 같은 기사 한 번만 | 원문 주소가 같거나, 띄어쓰기·기호를 뺀 제목이 같으면 (보도자료를 여러 언론사가 실은 경우) |
| 거르기·태그 | `rules.py` — 농업 기사 점수, 품목·작물 태그, 분류, 언론사 이름 |
| 저장 | `data/news.json` 최신순 90일 · `data/news-recent.json` 최근 7일 (화면용) |
| 기록 | `data/collect_log.json` (최근 100회: 받은·저장·거른 기사 수, 네이버 호출 수, 보유 기사 수, 오류), 이번에 거른 기사 `data/rejected.json` → 관리자 › 데이터 수집에서 그래프·목록으로 봄 |
| 실패 | 기존 기사는 그대로 두고 다음 수집 때 다시. 키 오류(401·403)면 바로 멈춤 |

## 규칙 고치기

- 단어 목록·점수 기준은 **`shared/news_rules.json`** 하나에 있습니다. 화면(frontend)도 같은 파일을 읽어서, 고치면 양쪽에 같이 반영됩니다.
- 잘못 걸러진 기사는 `data/rejected.json` 에서, 잘못 담긴 기사는 `data/news.json` 에서 찾아 단어를 더하거나 빼고 `--relabel` 로 확인합니다.
- 찾는 방식(함수)을 바꾸면 `frontend/src/utils/itemMatch.js`·`frontend/src/mocks/news.js` 도 똑같이 바꿔야 합니다.

## 저장 모양 (`data/news.json`)

```json
{
  "updated_at": "2026-10-22T18:00:03+09:00",
  "next_update_at": "2026-10-22T19:00:03+09:00",
  "count": 312,
  "articles": [
    { "id": "3f2a…", "title": "…", "summary": "…", "press": "연합뉴스", "url": "https://…",
      "published_at": "2026-10-22T17:41:00+09:00", "items": ["napa_cabbage"], "crops": [],
      "category": "가격·수급", "score": 7, "collected_at": "2026-10-22T18:00:01+09:00" }
  ]
}
```

DB 가 생기면 `save_news()` 만 테이블 저장으로 바꾸면 됩니다 (뉴스 테이블: `url` 고유, 제목·요약·언론사·발행 시각·분류·품목 목록 / 수집 기록: 마지막 성공 시각).

`data/news-recent.json` 은 최근 7일만 담은 화면용 파일입니다 (90일 전체는 수십 MB 가 되어 화면이 받기에 큼).

## 서버에서 돌리기

팀 서버 컴퓨터에서는 `docker compose` 의 `news-collector` 서비스로 1시간마다 돌고, 화면은 `http://서버주소/data/news-recent.json` 을 읽습니다 → **`deploy/README.md`**.

## 화면에서 보기

- 서버에 모인 기사: `frontend/.env` 에 `VITE_NEWS_URL=http://서버주소/data/news-recent.json`
- 내 PC 에서 돌린 기사: 프론트 테스트 모드(`VITE_DATA_SOURCE=live`)로 `npm run dev` 를 켜면 이 폴더의 `data/` 파일을 읽음 (없으면 네이버를 직접 부름)

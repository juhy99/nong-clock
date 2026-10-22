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
| 저장 | `data/news.json` 최신순, 90일 지난 기사는 지움 |
| 기록 | `data/collect_log.json` (최근 100회), 이번에 거른 기사 `data/rejected.json` |
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

## 화면에서 보기

프론트 테스트 모드(`VITE_DATA_SOURCE=live`)로 `npm run dev` 를 켜면 이 파일이 있을 때 화면 뉴스가 **수집한 기사**로 나옵니다 (없으면 네이버를 직접 부름).

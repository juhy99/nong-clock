# Frontend (React + Vite)

팜비드 웹 화면. 시세·경매·회원 기능은 Spring API가 생기기 전까지 **가짜 데이터**로 동작하고, AI 예측은 **ML API(FastAPI)에 실제로 연결**됩니다.

## 실행

```powershell
cd frontend
npm install        # 처음 한 번
npm run dev        # http://localhost:5173
```

- ML API도 같이 켜면 AI 예측이 실제 API 응답으로 나옵니다: `cd ml-api` → `python -m uvicorn app.main:app --reload`
- ML API가 꺼져 있으면 화면 위에 "데모 데이터" 안내가 뜨고 가짜 예측으로 대신 보여줍니다.
- API 주소를 바꾸려면 `.env.example`을 `.env`로 복사해서 `VITE_ML_API_BASE`를 고칩니다.

## 데모 계정 (로그인 화면에서 클릭하면 입력됨)

| 유형 | 이메일 | 비밀번호 |
|---|---|---|
| 구매자 | user@farmbid.kr | user1234 |
| 판매자 | farmer@farmbid.kr | farmer1234 |
| 관리자 (개발자 페이지) | admin@farmbid.kr | admin1234 |

회원가입·입찰·공지 작성 결과는 브라우저(localStorage)에만 저장됩니다. 개발자 페이지의 **데모 데이터 초기화**로 되돌릴 수 있습니다.

## 화면

| 주소 | 화면 | 데이터 |
|---|---|---|
| `/` | 홈 (시세 띠, 오늘의 시세, 날씨, 인기 경매, AI 급등락) | 가짜 + ML API |
| `/market` | 시세·수급 (표, 추이, 시장별, 수급) | 가짜 |
| `/ai` | AI 가격예측 | **ML API** |
| `/auctions`, `/auctions/:id` | 경매 목록·상세·입찰 | 가짜 |
| `/mypage` | 내 입찰·내 정보 (로그인 필요) | 가짜 |
| `/login`, `/signup` | 로그인·회원가입 (구매자/판매자) | 가짜 |
| `/admin/*` | 개발자 페이지: 서버·API 상태, 데이터 수집, 모델 성능, 신고·분쟁, 공지사항, 회원·경매 관리 (관리자만) | ML API 상태는 실제, 나머지 가짜 |

## 구조와 규칙

```
src/
  api/        서버 호출. 화면은 반드시 여기 함수만 부른다
    client.js   API 주소 (한 곳에서만 관리)
    ml.js       ML API — 실제 연결
    market.js · auction.js · auth.js · admin.js   Spring 담당 — 지금은 mocks/ 반환
  mocks/      가짜 데이터 (Spring API가 생기면 지운다)
  components/ 공통 부품 (레이아웃, 가격 변동 표시, 로딩·에러 처리)
  pages/      화면
  utils/format.js  가격(원/kg)·날짜 표시
```

- **Spring API 연결 방법:** `api/market.js` 등의 함수 안쪽만 `request(주소, "/api/...")` 로 바꾸면 됩니다. 화면 코드는 고칠 필요 없습니다. 응답 모양은 `docs/06_api_spec.md` 2번 섹션의 제안을 따릅니다.
- **품목·기간·지역은 하드코딩하지 않는다:** `GET /items`, `/horizons`, `/regions` 로 받아서 그립니다. 지역이 1개면 선택 박스를 숨깁니다.
- **가격 표기:** 모두 원/kg, 변동은 `▲ 80원 (+6.9%) 10/16(금) 대비` 처럼 비교 날짜를 함께 (`components/common.jsx` 의 `PriceChange`).
- ⚠️ 로그인·입찰 규칙 검사는 지금 프론트에서 흉내만 냅니다. 실제 검사는 반드시 Spring(서버)에서 해야 합니다.

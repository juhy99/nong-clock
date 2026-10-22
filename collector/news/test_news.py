"""뉴스 수집기 검사: python -m unittest -v  (collector/news 폴더에서)

- 규칙: 실제로 잘못 걸렀던 기사들이 다시 틀리지 않는지
- 수집: 가짜 네이버 서버로 한 번 수집 → 저장·중복 제거·거르기·다음 수집(새 기사만)·실패 처리
"""
import json
import threading
import unittest
from datetime import datetime, timedelta
from email.utils import format_datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import parse_qs, urlparse

import collect_news
import rules


class RulesTest(unittest.TestCase):
    def test_keep_or_drop(self):
        cases = [
            (False, "뜨끈한 시래기장어탕 단돈 1만원…장어돼지구이 맛집 '2TV 생생정보'", "보은대추축제는 지역 대표 특산물인 대추를 중심으로 다양한 농산물과 먹거리, 문화공연을 한자리에서 만날... 공개된 메뉴 정보에 따르면 1인분 가격은 1만원"),
            (False, "금리 고점은 늘 '부작용' 뒤에…금통위 동결, 끝 아닌 숨 고르기", "국채 수급(2023년)... 농산물·석유류를 뺀 근원물가는 2.7%다."),
            (False, "막판 돈풀기에 승부 거는 트럼프... 유권자들은 '패배 불복' 우려", "관세 정책으로 타격을 입은 농산물 재배 농가에 120억 달러의 구제 금융을 푼 데 이어 추가... 미국 평균 경유 가격은"),
            (False, "지뢰 도발 사과는커녕 적반하장 행보 지속하는 북한", "북한이 한반도의 군사적 긴장감 고조 책임을 우리 군에 떠넘기는 '적반하장'식 행보를 거듭하고 있다."),
            (False, "'과장님 대신 감자님'…청양군, 별명으로 공직사회 소통의 벽 낮춘다", "\"과장님\" 대신 \"감자님\", \"팀장님\" 대신 \"고구마님\"이라는 호칭이 등장하면서 색다른 변화가 시작됐다."),
            (False, "\"행정 실수로 물거품 죄송\"…유승민 회장, 체전 출전 무산 사과", "선수들에게 사과하라는 요구에 \"행정의 미숙함으로 선수들이 피해를 보고… 사과의 말씀을"),
            (False, "'김도영 만루포' KIA, LG 13대 1 대파...3연승으로 PO 진출", "KIA가 LG를 13대 1로 대파했다"),
            (False, "부산지검, 사기 혐의 업체 대표 기소", "부산지검은 피해자들에게 시세보다 높은 가격을 약속하며"),
            (True, "영덕군 '농업인대학 다축형 사과반' 수료식 개최", "지역 사과 산업을 이끌 맞춤형 전문 인재를 배출했다. 미래형 사과 재배 역량을"),
            (True, "가격 떨어진 샤인머스켓, 필리핀 수출길 열렸다", "생산량 증가와 소비 부진으로 샤인머스켓 가격이 떨어지는 가운데 농가 소득 안정에 나선... 재배농가와 송산농협 농산물산지유통센터"),
            (True, "배추값 급등", "고랭지 출하 줄어"),
            (True, "배 수출 물량 늘어… 신고배 미국·베트남 인기", "신고배 수출 물량이 지난해보다 늘었다."),
            (True, "청송군 명품 사과 출하량·가격 동반 하락…산지공판장 거래 위축", "사과 출하량이 줄었다"),
        ]
        for want, title, summary in cases:
            with self.subTest(title=title):
                self.assertEqual(rules.is_agri_news(title, summary), want)

    def test_item_tags(self):
        cases = [
            ("빅맥 1.7배 묵직", []), ("매출 3배 증가", []), ("칼로리 다섯 배 차이", []), ("레알은 배가 아프다", []),
            ("1-1 무, 승점 1", []), ("사과와 배, 단감", ["apple", "pear"]), ("고랭지 무값 하락", ["radish"]),
            ("배추 2배 올라", ["napa_cabbage"]), ("양배추 값", ["cabbage"]), ("양송이 서울시의원 예산", []),
        ]
        for text, want in cases:
            with self.subTest(text=text):
                self.assertEqual(rules.find_items(text), want)

    def test_crop_tags(self):
        self.assertEqual(rules.find_crops("샤인머스캣 가격 하락"), ["grape"])
        self.assertEqual(rules.find_crops("포도당 수치"), [])
        self.assertEqual(rules.find_crops("고추장 공장"), [])

    def test_clean_and_press(self):
        self.assertEqual(rules.clean("﻿<b>배추</b> &quot;출하&quot; "), '배추 "출하"')
        self.assertEqual(rules.press_of("https://www.yna.co.kr/view/1"), "연합뉴스")
        self.assertEqual(rules.press_of("https://m.example.com/a"), "example.com")


def article(title, desc, url, minutes_ago, now):
    return {"title": title, "description": desc, "originallink": url, "link": "https://n.news.naver.com/x",
            "pubDate": format_datetime(now - timedelta(minutes=minutes_ago))}


class FakeNaver(BaseHTTPRequestHandler):
    articles = []   # 모든 검색어에 같은 기사 목록을 돌려준다
    fail = False
    calls = []

    def do_GET(self):
        q = parse_qs(urlparse(self.path).query)
        FakeNaver.calls.append(q["query"][0])
        if FakeNaver.fail or self.headers.get("X-NCP-APIGW-API-KEY") != "secret":
            body, code = {"error": {"errorCode": "200", "message": "Authentication Failed", "details": "Invalid authentication information."}}, 401
        else:
            start, display = int(q["start"][0]), int(q["display"][0])
            body, code = {"items": FakeNaver.articles[start - 1:start - 1 + display]}, 200
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


class CollectTest(unittest.TestCase):
    def setUp(self):
        self.server = HTTPServer(("127.0.0.1", 0), FakeNaver)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.tmp = TemporaryDirectory()
        d = Path(self.tmp.name)
        self.saved = {k: getattr(collect_news, k) for k in ("API_URL", "NEWS_FILE", "RECENT_FILE", "LOG_FILE", "REJECTED_FILE", "CALL_GAP_SEC")}
        collect_news.API_URL = f"http://127.0.0.1:{self.server.server_port}/search/v1/news"
        collect_news.NEWS_FILE, collect_news.LOG_FILE, collect_news.REJECTED_FILE = d / "news.json", d / "log.json", d / "rejected.json"
        collect_news.RECENT_FILE = d / "news-recent.json"
        collect_news.CALL_GAP_SEC = 0
        collect_news.os.environ.update(NAVER_CLIENT_ID="id", NAVER_CLIENT_SECRET="secret")
        FakeNaver.fail, FakeNaver.calls = False, []
        now = collect_news.now()
        FakeNaver.articles = [
            article("<b>배추</b> 도매가 하락… 김장철 출하 늘어", "산지 출하가 늘며 가락시장 배추 값이 내렸다.", "https://www.yna.co.kr/1", 10, now),
            article("배추 도매가 하락…김장철 출하 늘어", "다른 언론사가 같은 보도자료를 실음", "https://www.news1.kr/2", 12, now),
            article("기업 대표 공식 사과문 발표", "재발 방지 약속", "https://example.com/3", 20, now),
        ]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        for k, v in self.saved.items():
            setattr(collect_news, k, v)
        self.tmp.cleanup()

    def read(self, path):
        return json.loads(path.read_text(encoding="utf-8"))

    def test_collect_then_only_new(self):
        r = collect_news.collect()
        self.assertTrue(r["ok"])
        news = self.read(collect_news.NEWS_FILE)
        self.assertEqual(news["count"], 1)  # 같은 제목 기사 한 번만, 사과문 기사는 거름
        a = news["articles"][0]
        self.assertEqual((a["title"], a["press"], a["items"], a["category"]), ("배추 도매가 하락… 김장철 출하 늘어", "연합뉴스", ["napa_cabbage"], "가격·수급"))
        self.assertEqual(len(self.read(collect_news.REJECTED_FILE)["articles"]), 1)
        self.assertEqual(self.read(collect_news.RECENT_FILE)["count"], 1)  # 화면용 최근 7일 파일도 함께
        self.assertEqual(len(FakeNaver.calls), len(rules.queries()))  # 처음엔 검색어마다 한 페이지

        # 다음 수집: 새 기사 하나만 더해지고, 이미 있는 기사는 다시 저장하지 않는다
        FakeNaver.articles.insert(0, article("양파 저장 물량 넉넉… 약보합 전망", "산지 출하 조절이 변수", "https://www.nongmin.com/4", 1, collect_news.now()))
        r2 = collect_news.collect()
        self.assertEqual(r2["added"], 1)
        self.assertEqual(self.read(collect_news.NEWS_FILE)["count"], 2)
        self.assertEqual(len(self.read(collect_news.LOG_FILE)["runs"]), 2)

    def test_failure_keeps_old_news(self):
        collect_news.collect()
        before = self.read(collect_news.NEWS_FILE)
        last = self.read(collect_news.LOG_FILE)["last_success_at"]
        FakeNaver.fail = True
        r = collect_news.collect()
        self.assertFalse(r["ok"])
        self.assertIn("Authentication Failed", r["errors"][0])
        self.assertEqual(self.read(collect_news.NEWS_FILE), before)                # 기존 기사 그대로
        self.assertEqual(self.read(collect_news.LOG_FILE)["last_success_at"], last)  # 다음엔 그 시각부터 다시

    def test_relabel(self):
        collect_news.collect()
        news = self.read(collect_news.NEWS_FILE)
        news["articles"][0]["items"] = []  # 예전 규칙으로 붙은 태그라고 가정
        news["articles"].append(dict(news["articles"][0], url="https://x/5", title="기업 대표 공식 사과문 발표", summary="재발 방지"))
        collect_news.write_json(collect_news.NEWS_FILE, news)
        collect_news.relabel()
        after = self.read(collect_news.NEWS_FILE)
        self.assertEqual(after["count"], 1)                             # 농업 기사가 아니게 된 것은 뺌
        self.assertEqual(after["articles"][0]["items"], ["napa_cabbage"])  # 태그 다시 붙임

    def test_recent_file_only_last_week(self):
        now = collect_news.now()
        rows = [{"published_at": (now - timedelta(days=d)).isoformat()} for d in (1, 6, 8, 30)]
        collect_news.save_news(rows, now)
        self.assertEqual(self.read(collect_news.NEWS_FILE)["count"], 4)
        self.assertEqual(self.read(collect_news.RECENT_FILE)["count"], 2)

    def test_old_articles_dropped(self):
        old = (collect_news.now() - timedelta(days=collect_news.KEEP_DAYS + 1)).isoformat()
        self.assertEqual(collect_news.drop_old([{"published_at": old}], collect_news.now()), [])


if __name__ == "__main__":
    unittest.main()

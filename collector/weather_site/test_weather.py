"""날씨 화면 파일 검사: python -m unittest -v  (collector/weather_site 폴더에서)

- v2 (날씨_대통합_일별.csv: 시도_일·시군구_일, 일별 평년값) 와 v1 (날씨_대통합.csv: 시도_일·시도_월) 모두
- 잘못된 파일·덜 써진 파일이면 기존 화면 파일을 지키는지, 수집기 기록 복사
"""
import csv
import json
import os
import time
import unittest
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

import export_weather as ew

COLS = ["구분", "기간", "날짜", "시도", "시군구", "위도", "경도", "평균기온", "최고기온", "최저기온", "강수량", "평균습도", "일조시간",
        "일사량", "최대풍속", "최대순간풍속", "최고극값", "최저극값", "고온일수", "영하일수", "강수일수", "강풍일수",
        "평년_평균기온", "평년_강수량", "지점수", "값개수"]


COLS_V2 = ["구분", "날짜", "시도", "시군구", "위도", "경도", "평균기온", "평균기온_근사", "최고기온", "최저기온", "강수량", "평균습도",
           "일조시간", "일사량", "최대풍속", "최대순간풍속", "평년_평균기온", "평년_최고기온", "평년_최저기온", "평년_강수량",
           "지점수", "지점수_ASOS", "지점수_AWS", "지점수_농업기상", "값개수"]


def write_csv(path, rows, bom=True, cols=COLS):
    with path.open("w", encoding="utf-8-sig" if bom else "utf-8", newline="") as f:
        w = csv.DictWriter(f, cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})


def sample_rows(days=150, months=30):
    rows = []
    end = date(2026, 10, 21)
    for sido in ew.SIDO:
        for i in range(days):
            d = end - timedelta(days=i)
            rows.append({"구분": "시도_일", "기간": "일", "날짜": d.isoformat(), "시도": sido, "평균기온": "12.345", "최고기온": "18",
                         "최저기온": "7", "강수량": "" if i == 0 else "0", "평균습도": "60", "일조시간": "6.5", "최대순간풍속": "9"})
        for i in range(months):
            y, m = divmod(2026 * 12 + 8 - i, 12)
            rows.append({"구분": "시도_월", "기간": "월", "날짜": f"{y}-{m + 1:02d}", "시도": sido, "평균기온": "15", "최고기온": "20",
                         "최저기온": "10", "강수량": "100", "고온일수": "0", "영하일수": "1", "강수일수": "5", "강풍일수": "0",
                         "평년_평균기온": str(10 + m), "평년_강수량": "80.5"})
    rows.append({"구분": "시군구_월", "기간": "월", "날짜": "2026-09", "시도": "전남", "시군구": "해남군", "최고기온": "25", "최저기온": "15", "강수량": "90"})
    return rows


def v2_rows(end=date(2026, 10, 21), days=800):
    """시군구_일 몇 줄 + 시도_일 (서울만 값을 바꿔 가며, 평년은 날짜마다 같은 값)"""
    rows = [{"구분": "시군구_일", "날짜": end.isoformat(), "시도": "전남", "시군구": "해남군", "최고기온": "20", "최저기온": "10", "강수량": "0"}]
    for sido in ew.SIDO:
        for i in range(days):
            d = end - timedelta(days=i)
            rain = "12" if d.day % 5 == 0 else "0"   # 한 달에 6번쯤 12mm
            rows.append({"구분": "시도_일", "날짜": d.isoformat(), "시도": sido,
                         "평균기온": "" if d.day == 1 else "10", "평균기온_근사": "40", "최고기온": "35" if d.month == 8 and d.day < 4 else "15",
                         "최저기온": "-2" if d.month == 1 and d.day < 6 else "5", "강수량": rain, "평균습도": "60", "일조시간": "6",
                         "최대순간풍속": "15" if d.day == 10 else "5", "평년_평균기온": str(d.month), "평년_강수량": "2.0"})
    return rows


class V2Test(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.csv = self.dir / "날씨_대통합_일별.csv"
        self.out = self.dir / "data"

    def tearDown(self):
        self.tmp.cleanup()

    def read(self, name):
        return json.loads((self.out / name).read_text(encoding="utf-8"))

    def test_v2(self):
        write_csv(self.csv, v2_rows(), cols=COLS_V2)
        meta = ew.export(self.csv, self.out)
        self.assertTrue(meta["ok"], meta.get("error"))
        self.assertEqual(meta["format"], "v2")
        self.assertEqual(meta["rows"]["시군구_일"], 1)

        last = self.read("regions-daily.json")["regions"]["서울"][-1]
        self.assertEqual(last["date"], "2026-10-21")
        self.assertEqual((last["normal_temp"], last["normal_rain"]), (10.0, 2.0))   # 그 날의 평년값
        first_of_month = next(d for d in self.read("regions-daily.json")["regions"]["서울"] if d["date"] == "2026-10-01")
        self.assertEqual(first_of_month["temp_avg"], 40.0)                          # 평균기온이 비면 근사값

        mo = self.read("regions-monthly.json")
        self.assertEqual(mo["last_month"], "2026-09")                               # 10월은 아직 안 끝남
        seoul = {m["month"]: m for m in mo["regions"]["서울"]}
        self.assertEqual(len(mo["regions"]["서울"]), ew.MONTHLY_MONTHS)
        self.assertEqual(seoul["2026-08"]["hot_days"], 3)
        self.assertEqual(seoul["2026-01"]["frost_days"], 5)
        self.assertEqual(seoul["2026-09"]["rain_mm"], 72.0)                         # 5·10·15·20·25·30일 × 12mm
        self.assertEqual(seoul["2026-09"]["rain_days"], 6)
        self.assertEqual(seoul["2026-09"]["windy_days"], 1)
        self.assertEqual(seoul["2026-09"]["temp_avg"], 11.0)                        # 1일만 근사 40 → (29×10 + 40)/30
        self.assertEqual(mo["normals"]["서울"]["9"], {"temp_avg": 9.0, "rain_mm": 60.0})   # 하루 2mm × 30일
        self.assertEqual(mo["normals"]["서울"]["2"]["rain_mm"], 56.0)              # 2월은 28일 (29일 빼고)

    def test_partial_month_has_no_value(self):
        write_csv(self.csv, [r for r in v2_rows() if not ("2026-07-01" <= r["날짜"] <= "2026-07-10")], cols=COLS_V2)
        self.assertTrue(ew.export(self.csv, self.out)["ok"])
        july = next(m for m in self.read("regions-monthly.json")["regions"]["서울"] if m["month"] == "2026-07")
        self.assertIsNone(july["temp_avg"])  # 관측일 21/31 < 80%

    def test_truncated_file_keeps_old(self):
        write_csv(self.csv, v2_rows(), cols=COLS_V2)
        ew.export(self.csv, self.out)
        before = (self.out / "regions-daily.json").read_text(encoding="utf-8")
        write_csv(self.csv, [r for r in v2_rows() if r["날짜"] < "2026-09-01"], cols=COLS_V2)  # 쓰다 만 파일
        meta = ew.export(self.csv, self.out)
        self.assertFalse(meta["ok"])
        self.assertIn("덜 써진 파일", meta["error"])
        self.assertEqual((self.out / "regions-daily.json").read_text(encoding="utf-8"), before)
        self.assertFalse(ew.changed(self.csv, self.out))  # 같은 파일은 바뀔 때까지 다시 안 읽음

    def test_copy_logs(self):
        logs = self.dir / "collector"
        logs.mkdir()
        (logs / "collect_log.json").write_text('{"runs":[]}', encoding="utf-8")
        self.assertEqual(ew.copy_logs(self.out, logs), 1)
        self.assertEqual(self.read("collect_log.json"), {"runs": []})
        self.assertEqual(ew.copy_logs(self.out, logs), 0)  # 안 바뀌면 복사 안 함


class ExportTest(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.csv = self.dir / "날씨_대통합.csv"
        self.out = self.dir / "data"

    def tearDown(self):
        self.tmp.cleanup()

    def read(self, name):
        return json.loads((self.out / name).read_text(encoding="utf-8"))

    def test_export(self):
        write_csv(self.csv, sample_rows())
        meta = ew.export(self.csv, self.out)
        self.assertTrue(meta["ok"], meta.get("error"))
        self.assertEqual(meta["ranges"]["시도_일"], [(date(2026, 10, 21) - timedelta(days=149)).isoformat(), "2026-10-21"])
        self.assertEqual(meta["ranges"]["시군구_월"], ["2026-09", "2026-09"])
        self.assertEqual(meta["rows"]["시도_일"], 150 * 17)

        daily = self.read("regions-daily.json")
        self.assertEqual(daily["last_date"], "2026-10-21")
        seoul = daily["regions"]["서울"]
        self.assertEqual(len(seoul), ew.DAILY_DAYS)                  # 최근 120일만
        self.assertEqual(seoul[-1]["date"], "2026-10-21")            # 오래된 날 → 최근 순
        self.assertEqual(seoul[-1]["temp_avg"], 12.3)                # 소수 1자리
        self.assertIsNone(seoul[-1]["rain_mm"])                      # 빈칸은 null (0 으로 채우지 않음)
        self.assertEqual(seoul[-2]["rain_mm"], 0)

        monthly = self.read("regions-monthly.json")
        self.assertEqual(monthly["last_month"], "2026-09")
        self.assertEqual(len(monthly["regions"]["제주"]), ew.MONTHLY_MONTHS)
        self.assertEqual(monthly["regions"]["제주"][-1]["month"], "2026-09")
        self.assertEqual(monthly["normals"]["제주"]["10"], {"temp_avg": 19.0, "rain_mm": 80.5})
        self.assertEqual(len(monthly["normals"]["제주"]), 12)

    def test_no_bom(self):
        write_csv(self.csv, sample_rows(days=3, months=2), bom=False)
        self.assertTrue(ew.export(self.csv, self.out)["ok"])

    def test_missing_file_keeps_old_files(self):
        write_csv(self.csv, sample_rows(days=3, months=2))
        ew.export(self.csv, self.out)
        before = (self.out / "regions-daily.json").read_text(encoding="utf-8")
        self.csv.unlink()
        meta = ew.export(self.csv, self.out)
        self.assertFalse(meta["ok"])
        self.assertIn("입력 파일이 없어요", meta["error"])
        self.assertEqual(meta["ranges"]["시도_일"], ["2026-10-19", "2026-10-21"])  # 지난번 기간은 남김
        self.assertEqual((self.out / "regions-daily.json").read_text(encoding="utf-8"), before)

    def test_bad_csv(self):
        self.csv.write_text("구분,날짜\n시도_일,2026-10-21\n", encoding="utf-8")
        meta = ew.export(self.csv, self.out)
        self.assertFalse(meta["ok"])
        self.assertIn("필요한 열이 없어요", meta["error"])
        self.assertFalse((self.out / "regions-daily.json").exists())

        write_csv(self.csv, [{"구분": "시도_일", "날짜": "2026-10-21", "시도": "서울특별시", "최고기온": "1"}])
        self.assertIn("모르는 시도 이름: 서울특별시", ew.export(self.csv, self.out)["error"])

    def test_find_csv(self):
        inp = self.dir / "input"
        inp.mkdir()
        self.assertIsNone(ew.find_csv(inp, env=False))
        a, b = inp / "날씨_대통합_1021.csv", inp / "날씨_대통합_1022.csv"
        a.write_text("x", encoding="utf-8")
        b.write_text("x", encoding="utf-8")
        os.utime(a, (time.time() + 9, time.time() + 9))
        self.assertEqual(ew.find_csv(inp, env=False), a)  # 이름과 상관없이 가장 최근 파일
        site = self.dir / "날씨_대통합_일별.csv"           # 서버: 수집기가 만든 표 (WEATHER_CSV)
        site.write_text("x", encoding="utf-8")
        os.utime(site, (time.time() + 20, time.time() + 20))
        os.environ["WEATHER_CSV"] = str(site)
        try:
            self.assertEqual(ew.find_csv(inp), site)
        finally:
            del os.environ["WEATHER_CSV"]

    def test_changed(self):
        write_csv(self.csv, sample_rows(days=3, months=2))
        self.assertTrue(ew.changed(self.csv, self.out))  # 아직 안 만듦
        self.assertFalse(ew.changed(self.csv, self.out, settle=60))  # 막 쓴 파일은 기다림
        ew.export(self.csv, self.out)
        self.assertFalse(ew.changed(self.csv, self.out))
        write_csv(self.csv, sample_rows(days=4, months=2))  # 데이터 담당이 새 CSV 를 씀
        later = time.time() + 5
        os.utime(self.csv, (later, later))
        self.assertTrue(ew.changed(self.csv, self.out))


if __name__ == "__main__":
    unittest.main()

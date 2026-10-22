"""인증 오류 → STOP 파일, 일시 오류 → STOP 없음, 키 없음 → 건너뜀 시험 (네트워크 필요 없음)

  python -m unittest tests/test_auth_stop.py -v

로컬 http.server를 띄우고 KMA_APIHUB_BASE·DATA_GO_KR_BASE 를 그 주소로 바꿔 run.py collect 를 실행함.
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
MODE = {'v': '401'}
GO_KR_ERR = ('<OpenAPI_ServiceResponse><cmmMsgHeader><errMsg>SERVICE ERROR</errMsg>'
             '<returnAuthMsg>{msg}</returnAuthMsg><returnReasonCode>{code}</returnReasonCode>'
             '</cmmMsgHeader></OpenAPI_ServiceResponse>')


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        m = MODE['v']
        if m == '401':
            self.send_response(401); self.end_headers(); self.wfile.write(b'Unauthorized'); return
        if m == '403':
            self.send_response(403); self.end_headers(); self.wfile.write(b'{"result":{"status":403}}'); return
        if m == '500':
            self.send_response(500); self.end_headers(); self.wfile.write(b'err'); return
        code, msg = {'code30': ('30', 'SERVICE_KEY_IS_NOT_REGISTERED_ERROR'),
                     'code22': ('22', 'LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR')}[m]
        body = GO_KR_ERR.format(code=code, msg=msg).encode()
        self.send_response(200); self.send_header('Content-Type', 'text/xml'); self.end_headers(); self.wfile.write(body)

    def log_message(self, *a):
        pass


class T(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = ThreadingHTTPServer(('127.0.0.1', 0), H)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.base = f'http://127.0.0.1:{cls.srv.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def run_collect(self, data, only, keys=True):
        env = {k: v for k, v in os.environ.items() if k not in ('KMA_APIHUB_KEY', 'KMA_AUTH_KEY', 'DATA_GO_KR_KEY')}
        env.update(DATA_DIR=str(data), KMA_APIHUB_BASE=self.base, DATA_GO_KR_BASE=self.base, RUN_LOCK_WAIT='5')
        if keys:
            env.update(KMA_APIHUB_KEY='dummy-kma', DATA_GO_KR_KEY='dummy-gokr')
        p = subprocess.run([sys.executable, str(HERE / 'run.py'), 'collect', '--only', only], env=env,
                           capture_output=True, text=True, timeout=600, cwd=str(data))
        log = json.loads((data / 'collect_log.json').read_text(encoding='utf-8'))
        return p, log['runs'][-1]

    def test_missing_key_skips(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            p, r = self.run_collect(d, 'asos,fcst', keys=False)
            self.assertEqual(p.returncode, 1)
            self.assertFalse(r['ok'])
            self.assertEqual(r['calls'], 0)
            self.assertEqual(r['sources']['asos']['skipped'], '키 없음')
            self.assertEqual(set(r) >= {'finished_at', 'ok', 'added', 'calls', 'errors'}, True)
            self.assertFalse(list(d.glob('STOP_*')))

    def test_http401_creates_stop_and_skips_next(self):
        MODE['v'] = '401'
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            p, r = self.run_collect(d, 'asos,aws,agri,fcst')
            self.assertEqual(r['sources']['asos']['exit'], 3)      # API허브 401 → 3
            self.assertEqual(r['sources']['agri']['exit'], 3)      # 공공데이터포털 401 → 3
            self.assertIn('STOP_KMA_APIHUB_KEY', [f.name for f in d.glob('STOP_*')])
            self.assertIn('STOP_DATA_GO_KR_KEY', [f.name for f in d.glob('STOP_*')])
            # 같은 키를 쓰는 aws·fcst는 같은 실행에서 바로 건너뜀
            self.assertIn('skipped', r['sources']['aws'])
            self.assertIn('skipped', r['sources']['fcst'])
            self.assertGreater(r['calls'], 0)
            # 다음 실행: 호출 0번, 건너뜀
            p2, r2 = self.run_collect(d, 'asos,agri')
            self.assertEqual(r2['calls'], 0)
            self.assertIn('skipped', r2['sources']['asos'])
            # STOP 파일을 지우면 다시 호출함
            for f in d.glob('STOP_*'):
                f.unlink()
            p3, r3 = self.run_collect(d, 'agri')
            self.assertGreater(r3['calls'], 0)

    def test_http403_apihub_aws(self):
        MODE['v'] = '403'
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            p, r = self.run_collect(d, 'aws')
            self.assertEqual(r['sources']['aws']['exit'], 3)
            self.assertTrue((d / 'STOP_KMA_APIHUB_KEY').exists())

    def test_gokr_code30_creates_stop(self):
        MODE['v'] = 'code30'
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            p, r = self.run_collect(d, 'fcst')
            self.assertEqual(r['sources']['fcst']['exit'], 3)
            self.assertEqual(r['sources']['fcst']['calls'], 1)    # 첫 호출에서 바로 멈춤
            self.assertTrue((d / 'STOP_DATA_GO_KR_KEY').exists())

    def test_quota_no_stop(self):
        MODE['v'] = 'code22'
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            p, r = self.run_collect(d, 'agri')
            self.assertEqual(r['sources']['agri']['exit'], 4)
            self.assertFalse(list(d.glob('STOP_*')))

    def test_http500_transient_no_stop(self):
        MODE['v'] = '500'
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            p, r = self.run_collect(d, 'agri')
            self.assertEqual(r['sources']['agri']['exit'], 1)
            self.assertFalse(r['ok'])
            self.assertTrue(r['errors'])
            self.assertFalse(list(d.glob('STOP_*')))
            # 다음 실행도 정상적으로 다시 시도함(잠금 남지 않음)
            p2, r2 = self.run_collect(d, 'agri')
            self.assertGreater(r2['calls'], 0)
            self.assertEqual(len(json.loads((d / 'collect_log.json').read_text(encoding='utf-8'))['runs']), 2)


if __name__ == '__main__':
    unittest.main()

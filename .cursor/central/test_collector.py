import importlib.util
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.error
import urllib.request


HERE = Path(__file__).resolve().parent


def load_collector(data_dir):
    os.environ["DATA_DIR"] = str(data_dir)
    os.environ["CENTRAL_DOMAIN"] = "fleet.example.test"
    os.environ.pop("COLLECTOR_TOKEN", None)
    os.environ.pop("COLLECTOR_TOKENS", None)
    spec = importlib.util.spec_from_file_location("collector_under_test", HERE / "collector.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CollectorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmp.name)
        self.collector = load_collector(self.data_dir)
        self.httpd = self.collector.ThreadingHTTPServer(("127.0.0.1", 0), self.collector.Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)
        self.tmp.cleanup()

    def request(self, path, method="GET", payload=None, token=None):
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(self.base + path, data=body, method=method)
        if body is not None:
            req.add_header("Content-Type", "application/json")
        if token:
            req.add_header("Authorization", "Bearer " + token)
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status, resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode("utf-8")

    def test_fleet_config_bootstraps_token_and_posts_run(self):
        status, body = self.request("/api/fleet-config")
        self.assertEqual(status, 200)
        cfg = json.loads(body)
        self.assertEqual(cfg["pushUrl"], "https://fleet.example.test/api/runs/<runId>")
        self.assertTrue(cfg["token"])
        self.assertTrue((self.data_dir / "fleet_push.token").is_file())

        status, _ = self.request("/api/runs/run-1", method="POST", payload={"status": "running"})
        self.assertEqual(status, 401)

        status, body = self.request(
            "/api/runs/run-1",
            method="POST",
            payload={"status": "running", "counts": {"done": 1, "total": 15}},
            token=cfg["token"],
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["runId"], "run-1")

        status, body = self.request("/api/runs")
        self.assertEqual(status, 200)
        runs = json.loads(body)["runs"]
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["runId"], "run-1")

    def test_run_id_sanitizer_removes_path_and_edge_punctuation(self):
        self.assertEqual(self.collector._safe_run_id("../bad id!!"), "bad-id")
        self.assertEqual(self.collector._safe_run_id("..."), None)
        self.assertEqual(self.collector._safe_run_id("ok.project_1"), "ok.project_1")


if __name__ == "__main__":
    unittest.main()

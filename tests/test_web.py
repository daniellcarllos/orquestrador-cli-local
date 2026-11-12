import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

from orchestrator import web


class WebTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        env = patch.dict(os.environ, {"ORCHESTRATOR_STATE_DIR": self.tmp.name})
        env.start()
        self.addCleanup(env.stop)
        self.server = web.make_server(port=0)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def get(self, path):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}") as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def write_history(self, lines):
        path = Path(self.tmp.name) / "history.jsonl"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def test_history_newest_first_and_ignores_bad_lines(self):
        self.write_history([
            json.dumps({"id": "a", "started_at": "2026-01-01T10:00:00+00:00", "agent": "codex"}),
            "{linha quebrada",
            json.dumps({"id": "b", "started_at": "2026-01-02T10:00:00+00:00", "agent": "claude"}),
            json.dumps({"sem": "id"}),
        ])
        status, data = self.get("/api/history")
        self.assertEqual(status, 200)
        self.assertEqual([e["id"] for e in data["entries"]], ["b", "a"])

    def test_history_missing_file_is_empty(self):
        self.assertEqual(self.get("/api/history"), (200, {"entries": []}))

    def test_plan_preview_without_execution_and_policy_restricted_to_examples(self):
        with patch("orchestrator.web.detect", return_value={"codex": "/c", "claude": "/a", "gemini": None}):
            status, data = self.get("/api/plan?task=revisar%20c%C3%B3digo&policy=policy.claude.example.json")
            self.assertEqual((status, data["agent"], data["model"]), (200, "claude", "opus"))
            status, data = self.get("/api/plan?task=x&policy=..%2F..%2Fpyproject.toml")
            self.assertEqual(status, 400)
            status, data = self.get("/api/plan?task=%20")
            self.assertEqual(status, 400)

    def test_doctor_without_probe_does_not_run_clis(self):
        with patch("orchestrator.web.detect", return_value={"codex": "/c", "claude": None, "gemini": None}), \
             patch("orchestrator.web.capabilities.inspect") as inspect:
            status, data = self.get("/api/doctor")
            inspect.assert_not_called()
        self.assertEqual((status, data["probed"], data["agents"]["codex"]["available"], data["agents"]["claude"]["available"]), (200, False, True, False))

    def test_static_rejects_traversal_and_only_get(self):
        with tempfile.TemporaryDirectory() as dist:
            Path(dist, "index.html").write_text("<html>painel</html>")
            with patch("orchestrator.web.DIST", Path(dist)):
                with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/qualquer/rota") as r:
                    self.assertIn(b"painel", r.read())  # SPA fallback
                with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/..%2F..%2Fetc%2Fpasswd") as r:
                    self.assertIn(b"painel", r.read())  # nunca sai de dist
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/api/history", method="POST", data=b"{}")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req)
        self.assertEqual(ctx.exception.code, 501)

    def test_server_only_binds_localhost(self):
        with self.assertRaises(ValueError):
            web.make_server(host="0.0.0.0", port=0)


if __name__ == "__main__":
    unittest.main()

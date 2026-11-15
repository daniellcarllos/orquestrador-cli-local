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
        self.server = web.make_server(port=0, token="tok-teste")
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def req(self, path, metodo="GET", corpo=None, token="tok-teste", cabecalhos=None):
        dados = None if corpo is None else (corpo if isinstance(corpo, bytes) else json.dumps(corpo).encode())
        h = {"X-Painel-Token": token} if token else {}
        if corpo is not None and not isinstance(corpo, bytes):
            h["Content-Type"] = "application/json"
        h.update(cabecalhos or {})
        r = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=dados, method=metodo, headers=h)
        try:
            with urllib.request.urlopen(r) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def get(self, path):
        return self.req(path)

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
        status, _ = self.req("/api/history", "POST", {})
        self.assertEqual(status, 404)

    def test_catalogo_sem_expor_chaves(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-segredo-que-nao-pode-vazar"}):
            status, data = self.get("/api/catalogo")
        self.assertEqual(status, 200)
        self.assertTrue(data["provedores"]["anthropic"])
        self.assertIn("forte", data["niveis"])
        self.assertNotIn("segredo", json.dumps(data))

    def test_api_exige_token_host_e_origem(self):
        self.assertEqual(self.req("/api/history", token=None)[0], 401)
        self.assertEqual(self.req("/api/history", token="errado")[0], 401)
        self.assertEqual(self.req("/api/history", cabecalhos={"Host": "evil.example:80"})[0], 403)
        status, _ = self.req("/api/repositorios", "PUT", {"favoritos": []}, cabecalhos={"Origin": "http://evil.example"})
        self.assertEqual(status, 403)
        status, _ = self.req("/api/repositorios", "PUT", b"favoritos=x", cabecalhos={"Content-Type": "application/x-www-form-urlencoded"})
        self.assertEqual(status, 400)
        self.assertEqual(self.req("/api/repositorios", "PUT", {"favoritos": []}, cabecalhos={"Origin": f"http://127.0.0.1:{self.port}"})[0], 200)

    def test_repositorio_e_favoritos(self):
        repo = Path(self.tmp.name) / "repo"
        repo.mkdir()
        status, info = self.get(f"/api/repositorio?caminho={repo}")
        self.assertEqual((status, info["git"]), (200, False))
        self.assertEqual(self.get("/api/repositorio?caminho=relativo")[0], 400)
        status, data = self.req("/api/repositorios", "PUT", {"favoritos": [str(repo), str(repo)]})
        self.assertEqual(data["favoritos"], [str(repo.resolve())])
        self.assertEqual(self.req("/api/repositorios", "PUT", {"favoritos": ["/nao/existe"]})[0], 400)

    def test_catalogo_do_usuario_validado(self):
        status, cat = self.get("/api/catalogo")
        self.assertFalse(cat["do_usuario"])
        novo = {"versao": "meu-1", "niveis": cat["niveis"], "alternativos": {}, "precos_por_milhao": {}}
        status, salvo = self.req("/api/catalogo", "PUT", novo)
        self.assertEqual((status, salvo["versao"], salvo["do_usuario"]), (200, "meu-1", True))
        self.assertEqual(oct((Path(self.tmp.name) / "modelos.json").stat().st_mode & 0o777), "0o600")
        self.assertEqual(self.req("/api/catalogo", "PUT", {"versao": "x"})[0], 400)
        self.assertFalse(self.req("/api/catalogo", "DELETE")[1]["do_usuario"])

    def test_resultado_rejeita_id_invalido(self):
        self.assertEqual(self.get("/api/resultados/..%2F..%2Fetc")[0], 400)
        self.assertEqual(self.get("/api/execucoes/inexistente")[0], 404)

    def test_server_only_binds_localhost(self):
        with self.assertRaises(ValueError):
            web.make_server(host="0.0.0.0", port=0)


if __name__ == "__main__":
    unittest.main()

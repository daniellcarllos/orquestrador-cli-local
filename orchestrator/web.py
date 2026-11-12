"""Painel local somente de leitura: serve o front em web/dist e uma API mínima sobre o histórico.

Só biblioteca padrão. Escuta apenas em 127.0.0.1, não executa CLIs de agentes (exceto `--help`
no inventário, sob demanda) e não aceita métodos além de GET.
"""

from __future__ import annotations

import json
import mimetypes
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from . import capabilities
from .cli import history_path
from .core import detect, load_policy, plan

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "web" / "dist"
POLICIES = ROOT / "examples" / "policies"
HISTORY_LIMIT = 500
PROBE_TTL = 300  # segundos de cache do inventário com --probe

_probe_cache: dict = {"at": 0.0, "data": None}
_probe_lock = threading.Lock()


def read_history(limit: int = HISTORY_LIMIT) -> list[dict]:
    """Últimas entradas do histórico, mais recentes primeiro; linhas inválidas são ignoradas."""
    path = history_path()
    if not path.exists():
        return []
    entries = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                entries.append(item)
    entries.sort(key=lambda e: e.get("started_at") or "")  # estável: linhas sem data mantêm a ordem do arquivo
    return entries[-limit:][::-1]


def inventory(probe: bool) -> dict:
    found = detect()
    if not probe:
        return {"agents": {k: {"available": bool(v)} for k, v in found.items()}, "probed": False}
    with _probe_lock:
        if _probe_cache["data"] is None or time.monotonic() - _probe_cache["at"] > PROBE_TTL:
            data = {k: capabilities.inspect(k, v, ROOT) if v else {"available": False} for k, v in found.items()}
            for k, v in found.items():
                data[k]["available"] = bool(v)
            _probe_cache.update(at=time.monotonic(), data=data)
        return {"agents": _probe_cache["data"], "probed": True}


def policies() -> list[str]:
    return sorted(p.name for p in POLICIES.glob("*.json")) if POLICIES.is_dir() else []


def preview(task: str, policy_name: str | None) -> dict:
    """Classificação e roteamento sem efeitos; a política só pode vir de examples/policies."""
    policy = None
    if policy_name:
        if policy_name not in policies():
            raise ValueError("Política desconhecida.")
        policy = load_policy(POLICIES / policy_name)
    return plan(task, detect(), None, policy).as_dict()


class Handler(BaseHTTPRequestHandler):
    server_version = "orquestrador-painel/0.1"

    def log_message(self, *args):  # silencioso: nada de tarefas no terminal
        pass

    def do_GET(self):
        url = urlsplit(self.path)
        try:
            if url.path.startswith("/api/"):
                self.api(url.path, parse_qs(url.query))
            else:
                self.static(url.path)
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def api(self, path: str, query: dict):
        if path == "/api/history":
            self.send_json({"entries": read_history()})
        elif path == "/api/doctor":
            self.send_json(inventory(query.get("probe", ["0"])[0] == "1"))
        elif path == "/api/policies":
            self.send_json({"policies": policies()})
        elif path == "/api/plan":
            task = query.get("task", [""])[0]
            if not task.strip() or len(task) > 4000:
                raise ValueError("Informe uma tarefa com até 4000 caracteres.")
            self.send_json(preview(task, query.get("policy", [None])[0]))
        else:
            self.send_json({"error": "Rota desconhecida."}, HTTPStatus.NOT_FOUND)

    def static(self, path: str):
        if not DIST.is_dir():
            self.send_json({"error": "Front não compilado: rode `npm run build` em web/."}, HTTPStatus.SERVICE_UNAVAILABLE)
            return
        relative = path.lstrip("/") or "index.html"
        target = (DIST / relative).resolve()
        if not target.is_relative_to(DIST) or not target.is_file():
            target = DIST / "index.html"  # SPA
        if not target.is_file():
            self.send_json({"error": "index.html ausente."}, HTTPStatus.NOT_FOUND)
            return
        body = target.read_bytes()
        content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, data, status=HTTPStatus.OK):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)


def make_server(host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError("O painel só escuta em localhost.")
    return ThreadingHTTPServer((host, port), Handler)


def serve(host: str = "127.0.0.1", port: int = 8765) -> int:
    server = make_server(host, port)
    print(f"Painel do orquestrador em http://{host}:{server.server_address[1]}/  (Ctrl+C para sair)")
    if not DIST.is_dir():
        print("Aviso: web/dist não existe; só a API responderá. Rode `npm install && npm run build` em web/.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


__all__ = ["serve", "make_server", "read_history", "inventory", "preview", "policies"]

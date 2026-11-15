"""Painel local: serve o front em web/dist e a API que lê o histórico e dispara execuções.

Só biblioteca padrão. Proteções, já que qualquer página aberta no navegador consegue falar com
127.0.0.1:
- escuta só em localhost e confere o cabeçalho Host (bloqueia DNS rebinding);
- toda rota /api exige o token de sessão gerado a cada `serve` (enviado no cabeçalho X-Painel-Token);
- escrita só com corpo JSON e Origin do próprio painel (bloqueia formulários de outros sites);
- execuções rodam o próprio CLI em subprocesso, com argumentos validados (ver jobs.py).
"""

from __future__ import annotations

import hmac
import json
import mimetypes
import os
import re
import secrets
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from ..cli import history_path
from ..terminal import capabilities
from ..terminal.core import detect, load_policy, plan
from . import jobs

ROOT = Path(__file__).resolve().parents[2]
DIST = ROOT / "web" / "dist"
POLICIES = ROOT / "examples" / "policies"
HISTORY_LIMIT = 500
PROBE_TTL = 300  # segundos de cache do inventário com --probe
MAX_CORPO = 200_000
_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

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


def _catalogo_efetivo() -> tuple[dict | None, bool]:
    from ..api import modelos

    usuario = jobs.catalogo_usuario()
    try:
        if usuario.is_file():
            return modelos.carregar(usuario), True
        return modelos.carregar(), False
    except ValueError:
        return None, usuario.is_file()


def catalogo() -> dict:
    """Catálogo em uso (do usuário, se existir) e quais provedores têm chave (só sim/não)."""
    from ..api import modelos

    c, do_usuario = _catalogo_efetivo()
    base = {"provedores": modelos.provedores_configurados(), "do_usuario": do_usuario}
    if c is None:
        return {"versao": None, "niveis": {}, "alternativos": {}, "precos_por_milhao": {}, **base}
    return {"versao": c["versao"], "niveis": c["niveis"], "alternativos": c.get("alternativos", {}),
            "precos_por_milhao": c.get("precos_por_milhao", {}), **base}


def salvar_catalogo(dados: dict) -> dict:
    from ..api import modelos

    modelos.validar(dados)
    caminho = jobs.catalogo_usuario()
    caminho.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(caminho, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)
    return catalogo()


def ambiente() -> dict:
    try:
        import agno  # noqa: F401

        tem_agno = True
    except ImportError:
        tem_agno = False
    return {"agno": tem_agno, "max_simultaneas": jobs.MAX_SIMULTANEAS, "politicas": policies(),
            "acoes": list(jobs.ACOES)}


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


def resultado(execucao_id: str) -> dict:
    from ..api import registro

    meta = registro.ler(execucao_id)
    pasta = registro.pasta_execucoes() / execucao_id
    texto = (pasta / "resultado.md").read_text(encoding="utf-8") if (pasta / "resultado.md").is_file() else ""
    estruturado = None
    if (pasta / "resultado.json").is_file():
        estruturado = json.loads((pasta / "resultado.json").read_text(encoding="utf-8"))
    propostas = []
    for p in sorted(pasta.glob("proposta-*")):
        manifesto = p / "manifest.json"
        if p.is_dir() and manifesto.is_file():
            propostas.append({"nome": p.name, "caminho": str(p), **json.loads(manifesto.read_text(encoding="utf-8"))})
    return {"meta": meta, "markdown": texto, "estruturado": estruturado, "propostas": propostas, "pasta": str(pasta)}


class Handler(BaseHTTPRequestHandler):
    server_version = "orquestrador-painel/0.2"

    def log_message(self, *args):  # silencioso: nada de tarefas no terminal
        pass

    # ---------- proteção ----------
    def _host_ok(self) -> bool:
        porta = self.server.server_address[1]
        return self.headers.get("Host", "") in {f"127.0.0.1:{porta}", f"localhost:{porta}", f"[::1]:{porta}"}

    def _origem_ok(self) -> bool:
        origem = self.headers.get("Origin")
        if origem is None:
            return True
        porta = self.server.server_address[1]
        return origem in {f"http://127.0.0.1:{porta}", f"http://localhost:{porta}"}

    def _token_ok(self) -> bool:
        return hmac.compare_digest(self.headers.get("X-Painel-Token", ""), self.server.token)

    def _corpo(self) -> dict:
        if not self.headers.get("Content-Type", "").startswith("application/json"):
            raise ValueError("Envie JSON.")
        tamanho = int(self.headers.get("Content-Length") or 0)
        if tamanho > MAX_CORPO:
            raise ValueError("Corpo grande demais.")
        dados = json.loads(self.rfile.read(tamanho) or b"{}")
        if not isinstance(dados, dict):
            raise ValueError("Corpo inválido.")
        return dados

    def _despachar(self, metodo: str):
        if not self._host_ok():
            self.send_json({"error": "Host não permitido."}, HTTPStatus.FORBIDDEN)
            return
        url = urlsplit(self.path)
        if not url.path.startswith("/api/"):
            if metodo != "GET":
                self.send_json({"error": "Método não permitido."}, HTTPStatus.METHOD_NOT_ALLOWED)
            else:
                self.static(url.path)
            return
        if not self._token_ok():
            self.send_json({"error": "Token do painel ausente ou inválido. Abra o endereço exibido pelo serve."}, HTTPStatus.UNAUTHORIZED)
            return
        if metodo != "GET" and not self._origem_ok():
            self.send_json({"error": "Origem não permitida."}, HTTPStatus.FORBIDDEN)
            return
        try:
            corpo = self._corpo() if metodo in ("POST", "PUT") else {}
            self.api(metodo, url.path, parse_qs(url.query), corpo)
        except KeyError as exc:
            self.send_json({"error": str(exc.args[0]) if exc.args else "Não encontrado."}, HTTPStatus.NOT_FOUND)
        except (ValueError, json.JSONDecodeError) as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def do_GET(self):
        self._despachar("GET")

    def do_POST(self):
        self._despachar("POST")

    def do_PUT(self):
        self._despachar("PUT")

    def do_DELETE(self):
        self._despachar("DELETE")

    # ---------- rotas ----------
    def api(self, metodo: str, path: str, query: dict, corpo: dict):
        g = self.server.gerenciador
        rota = (metodo, path)
        partes = path.strip("/").split("/")  # api, recurso, id, subrecurso

        if rota == ("GET", "/api/history"):
            return self.send_json({"entries": read_history()})
        if rota == ("GET", "/api/doctor"):
            return self.send_json(inventory(query.get("probe", ["0"])[0] == "1"))
        if rota == ("GET", "/api/catalogo"):
            return self.send_json(catalogo())
        if rota == ("PUT", "/api/catalogo"):
            return self.send_json(salvar_catalogo(corpo))
        if rota == ("DELETE", "/api/catalogo"):
            jobs.catalogo_usuario().unlink(missing_ok=True)
            return self.send_json(catalogo())
        if rota == ("GET", "/api/policies"):
            return self.send_json({"policies": policies()})
        if rota == ("GET", "/api/ambiente"):
            return self.send_json(ambiente())
        if rota == ("GET", "/api/plan"):
            task = query.get("task", [""])[0]
            if not task.strip() or len(task) > 4000:
                raise ValueError("Informe uma tarefa com até 4000 caracteres.")
            return self.send_json(preview(task, query.get("policy", [None])[0]))
        if rota == ("GET", "/api/repositorio"):
            return self.send_json(jobs.info_repositorio(query.get("caminho", [""])[0]))
        if rota == ("GET", "/api/repositorios"):
            return self.send_json({"favoritos": jobs.favoritos()})
        if rota == ("PUT", "/api/repositorios"):
            lista = corpo.get("favoritos")
            if not isinstance(lista, list):
                raise ValueError("Envie a lista de favoritos.")
            return self.send_json({"favoritos": jobs.salvar_favoritos(lista)})
        if rota == ("POST", "/api/plano"):
            return self.send_json(g.plano(corpo))
        if rota == ("POST", "/api/execucoes"):
            return self.send_json(g.iniciar(corpo).as_dict(), HTTPStatus.CREATED)
        if rota == ("GET", "/api/execucoes"):
            return self.send_json({"execucoes": g.lista(), "ativas": g.ativos()})
        if len(partes) >= 3 and partes[1] == "execucoes":
            if metodo == "GET" and len(partes) == 3:
                return self.send_json(g.obter(partes[2]).as_dict())
            if metodo == "POST" and len(partes) == 4 and partes[3] == "cancelar":
                return self.send_json(g.cancelar(partes[2]).as_dict())
        if len(partes) >= 3 and partes[1] == "resultados":
            execucao = partes[2]
            if not _UUID.fullmatch(execucao):
                raise ValueError("Id de execução inválido.")
            if metodo == "GET" and len(partes) == 3:
                return self.send_json(resultado(execucao))
            if metodo == "POST" and len(partes) == 4 and partes[3] == "acao":
                return self.send_json(self._acao(execucao, corpo))
            if metodo == "POST" and len(partes) == 4 and partes[3] == "aplicar":
                return self.send_json(self._aplicar(execucao, corpo))
        self.send_json({"error": "Rota desconhecida."}, HTTPStatus.NOT_FOUND)

    def _acao(self, execucao: str, corpo: dict) -> dict:
        if corpo.get("confirmado") is not True:
            raise ValueError("Confirme a ação.")
        nome, especificacao = jobs._acao(corpo.get("acao"))
        codigo, saida = jobs.rodar_cli(["acao", execucao, especificacao, f"--aprovar-acoes={nome}"])
        try:
            return {"ok": codigo == 0, **json.loads(saida[saida.index("{"):])}
        except ValueError:
            return {"ok": False, "saida": saida}

    def _aplicar(self, execucao: str, corpo: dict) -> dict:
        if corpo.get("confirmado") is not True:
            raise ValueError("Confirme a aplicação do patch.")
        from ..api import registro

        pasta = (registro.pasta_execucoes() / execucao).resolve()
        proposta = (pasta / str(corpo.get("proposta", ""))).resolve()
        if proposta.parent != pasta or not proposta.name.startswith("proposta-") or not proposta.is_dir():
            raise ValueError("Proposta inválida.")
        sha = str(corpo.get("sha256", ""))
        if not re.fullmatch(r"[0-9a-f]{64}", sha):
            raise ValueError("SHA-256 inválido.")
        repo = jobs.validar_repositorio(corpo.get("repositorio"))
        codigo, saida = jobs.rodar_cli(["apply", str(proposta), f"--cwd={repo}", f"--approve-sha256={sha}"])
        return {"ok": codigo == 0, "saida": saida}

    # ---------- arquivos estáticos ----------
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
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
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


def make_server(host: str = "127.0.0.1", port: int = 8765, token: str | None = None) -> ThreadingHTTPServer:
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError("O painel só escuta em localhost.")
    server = ThreadingHTTPServer((host, port), Handler)
    server.token = token or secrets.token_urlsafe(24)
    server.gerenciador = jobs.Gerenciador()
    return server


def serve(host: str = "127.0.0.1", port: int = 8765) -> int:
    server = make_server(host, port, os.environ.get("ORCHESTRATOR_PAINEL_TOKEN") or None)
    porta = server.server_address[1]
    print(f"Painel do orquestrador: http://{host}:{porta}/#token={server.token}")
    print("Abra exatamente esse endereço (o token muda a cada inicialização). Ctrl+C para sair.")
    if not DIST.is_dir():
        print("Aviso: web/dist não existe; só a API responderá. Rode `npm install && npm run build` em web/.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        for job in list(server.gerenciador.jobs.values()):
            if job.status == "executando":
                server.gerenciador.cancelar(job.id)
        server.server_close()
    return 0


__all__ = ["serve", "make_server", "read_history", "inventory", "preview", "policies", "catalogo"]

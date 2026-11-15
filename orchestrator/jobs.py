"""Execuções disparadas pelo painel: validação do pedido, linha de comando e acompanhamento.

O painel nunca chama modelos diretamente: ele roda o próprio CLI (`python -m orchestrator ...`) em
subprocesso, com lista de argumentos (sem shell). Textos livres vão depois de `--` e valores de
opções no formato `--opcao=valor`, para que nada digitado vire uma opção. Só os fluxos e opções
listados aqui são aceitos.
"""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .cli import history_path

ROOT = Path(__file__).resolve().parent.parent
POLITICAS = ROOT / "examples" / "policies"
FLUXOS_API = ("revisar", "analisar", "desenvolver", "equipe")
FLUXOS = (*FLUXOS_API, "cli")
ACOES = ("notificar", "comentar_pr_azure", "comentar_pr_github", "salvar_na_biblioteca")
MAX_SIMULTANEAS = 2
MAX_TEXTO = 4000
_REF = re.compile(r"^[A-Za-z0-9._/@~^-]{1,120}$")
_ID_MCP = re.compile(r"^[a-f0-9]{10}$")
_PARAM = re.compile(r"^[a-z_]{1,20}$")
_VALOR = re.compile(r"^[^\s,=:]{1,200}$")


def pasta_estado() -> Path:
    return history_path().parent


def catalogo_usuario() -> Path:
    return pasta_estado() / "modelos.json"


# ------------------------------ validação ------------------------------

def _texto(v, nome: str, obrigatorio: bool = True) -> str | None:
    if v is None or (isinstance(v, str) and not v.strip()):
        if obrigatorio:
            raise ValueError(f"Informe {nome}.")
        return None
    if not isinstance(v, str) or len(v) > MAX_TEXTO or "\x00" in v:
        raise ValueError(f"{nome} inválido (até {MAX_TEXTO} caracteres).")
    return v.strip()


def _numero(v, nome: str, minimo: float, maximo: float, inteiro: bool = False):
    if v is None or v == "":
        return None
    try:
        n = int(v) if inteiro else float(v)
    except (TypeError, ValueError):
        raise ValueError(f"{nome} deve ser numérico.") from None
    if not minimo <= n <= maximo:
        raise ValueError(f"{nome} deve estar entre {minimo} e {maximo}.")
    return n


def _ref(v, nome: str) -> str | None:
    if v in (None, ""):
        return None
    if not isinstance(v, str) or not _REF.fullmatch(v) or v.startswith("-") or ".." in v:
        raise ValueError(f"{nome} inválido.")
    return v


def validar_repositorio(caminho) -> Path:
    if not isinstance(caminho, str) or not caminho.strip() or len(caminho) > 1000:
        raise ValueError("Informe o caminho do repositório.")
    p = Path(os.path.expanduser(caminho.strip()))
    if not p.is_absolute():
        raise ValueError("Use o caminho absoluto do repositório.")
    p = p.resolve()
    if not p.is_dir():
        raise ValueError("Repositório não encontrado.")
    return p


def _acao(item) -> tuple[str, str]:
    if not isinstance(item, dict) or item.get("acao") not in ACOES:
        raise ValueError("Ação desconhecida.")
    params = item.get("params") or {}
    if not isinstance(params, dict):
        raise ValueError("Parâmetros da ação inválidos.")
    partes = []
    for k, v in params.items():
        v = str(v).strip()
        if not v:
            continue
        if not _PARAM.fullmatch(k) or not _VALOR.fullmatch(v):
            raise ValueError(f"Parâmetro inválido na ação {item['acao']}: {k}")
        partes.append(f"{k}={v}")
    return item["acao"], item["acao"] + (":" + ",".join(partes) if partes else "")


def montar_comando(pedido: dict, *, so_plano: bool = False, resumo: Path | None = None) -> list[str]:
    """Pedido do painel → argv do CLI. Levanta ValueError para qualquer coisa fora do previsto."""
    if not isinstance(pedido, dict):
        raise ValueError("Pedido inválido.")
    fluxo = pedido.get("fluxo")
    if fluxo not in FLUXOS:
        raise ValueError("Fluxo desconhecido.")
    repo = validar_repositorio(pedido.get("repositorio"))
    argv = [sys.executable, "-m", "orchestrator"]
    posicional: list[str] = []

    if fluxo == "cli":
        agente = pedido.get("agente")
        if agente not in (None, "", "codex", "claude", "gemini"):
            raise ValueError("Agente de terminal desconhecido.")
        argv += ["run", f"--cwd={repo}"]
        if agente:
            argv.append(f"--agent={agente}")
        politica = pedido.get("politica")
        if politica:
            if politica not in {p.name for p in POLITICAS.glob("*.json")}:
                raise ValueError("Política desconhecida.")
            argv.append(f"--policy={POLITICAS / politica}")
        timeout = _numero(pedido.get("timeout"), "Tempo limite", 10, 3600, inteiro=True)
        if timeout:
            argv.append(f"--timeout={timeout}")
        argv.append("--approve")
        return argv + ["--", _texto(pedido.get("texto"), "a tarefa")]

    argv += [fluxo, f"--cwd={repo}"]
    if fluxo == "revisar":
        base, head = _ref(pedido.get("base"), "Base"), _ref(pedido.get("head"), "Head")
        diff = pedido.get("diff_arquivo")
        if diff:
            caminho = validar_repositorio(str(Path(os.path.expanduser(diff)).parent)) / Path(diff).name
            if not caminho.is_file():
                raise ValueError("Arquivo de diff não encontrado.")
            argv.append(f"--diff={caminho}")
        elif base:
            argv.append(f"--base={base}")
            if head:
                argv.append(f"--head={head}")
        else:
            raise ValueError("Informe a branch base ou um arquivo de diff.")
        mcp = pedido.get("mcp") or {}
        if mcp.get("prompt_id"):
            if not _ID_MCP.fullmatch(str(mcp["prompt_id"])):
                raise ValueError("ID de prompt MCP inválido.")
            argv += [f"--mcp-prompt-id={mcp['prompt_id']}",
                     f"--mcp-project={_texto(mcp.get('projeto'), 'o projeto MCP')}",
                     f"--mcp-group={_texto(mcp.get('grupo'), 'o grupo MCP')}"]
    elif fluxo == "analisar":
        posicional = [_texto(pedido.get("texto"), "a pergunta")]
        n = _numero(pedido.get("max_areas"), "Máximo de áreas", 1, 8, inteiro=True)
        if n:
            argv.append(f"--max-areas={n}")
    elif fluxo == "desenvolver":
        posicional = [_texto(pedido.get("texto"), "o objetivo")]
        teste = _texto(pedido.get("teste"), "o comando de teste", obrigatorio=False)
        if teste:
            if len(teste) > 200 or "\n" in teste:
                raise ValueError("Comando de teste inválido.")
            argv.append(f"--teste={teste}")
        n = _numero(pedido.get("max_subtarefas"), "Máximo de subtarefas", 1, 6, inteiro=True)
        if n:
            argv.append(f"--max-subtarefas={n}")
    elif fluxo == "equipe":
        posicional = [_texto(pedido.get("texto"), "a tarefa")]
        modo = pedido.get("modo") or "coordinate"
        if modo not in ("coordinate", "route", "broadcast"):
            raise ValueError("Modo de equipe inválido.")
        argv.append(f"--modo={modo}")

    cfg = pedido.get("config") or {}
    for chave, opcao, minimo, maximo, inteiro in (("teto_usd", "--teto-usd", 0.01, 100, False),
                                                  ("teto_tokens", "--teto-tokens", 1000, 5_000_000, True),
                                                  ("teto_dia_usd", "--teto-dia-usd", 0.01, 1000, False)):
        v = _numero(cfg.get(chave), chave, minimo, maximo, inteiro)
        if v is not None:
            argv.append(f"{opcao}={v}")
    if cfg.get("nivel_forcado"):
        if cfg["nivel_forcado"] not in ("leve", "medio", "forte"):
            raise ValueError("Nível forçado inválido.")
        argv.append(f"--nivel-forcado={cfg['nivel_forcado']}")
    if cfg.get("simulado"):
        argv.append("--simulado")
    if catalogo_usuario().is_file():
        argv.append(f"--catalogo={catalogo_usuario()}")

    aprovadas = set()
    for item in pedido.get("acoes") or []:
        nome, especificacao = _acao(item)
        argv.append(f"--ao-finalizar={especificacao}")
        if item.get("aprovada"):
            aprovadas.add(nome)
    for nome in sorted(aprovadas):
        argv.append(f"--aprovar-acoes={nome}")

    argv.append("--so-plano" if so_plano else "--approve")
    if resumo is not None:
        argv.append(f"--resumo-arquivo={resumo}")
    return argv + (["--", *posicional] if posicional else [])


# ------------------------------ execução ------------------------------

@dataclass
class Job:
    id: str
    fluxo: str
    titulo: str
    argv: list[str]
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))
    status: str = "executando"  # executando | ok | interrompido | erro | cancelado
    execucao: str | None = None
    saida: str = ""
    log: deque = field(default_factory=lambda: deque(maxlen=200))
    codigo: int | None = None
    processo: subprocess.Popen | None = None
    resumo: Path | None = None
    fim: float | None = None
    inicio: float = field(default_factory=time.monotonic)

    def as_dict(self) -> dict:
        self._ler_resumo()
        return {"id": self.id, "fluxo": self.fluxo, "titulo": self.titulo, "started_at": self.started_at,
                "status": self.status, "execucao": self.execucao, "codigo": self.codigo,
                "duracao_ms": round(((self.fim or time.monotonic()) - self.inicio) * 1000),
                "log": list(self.log)[-60:], "saida": self.saida[-20_000:] if self.fluxo == "cli" else ""}

    def _ler_resumo(self) -> None:
        if self.resumo and self.resumo.is_file() and not self.execucao:
            try:
                self.execucao = json.loads(self.resumo.read_text(encoding="utf-8")).get("execucao")
            except (OSError, json.JSONDecodeError):
                pass


class Gerenciador:
    def __init__(self, maximo: int = MAX_SIMULTANEAS):
        self.jobs: dict[str, Job] = {}
        self.maximo = maximo
        self._lock = threading.Lock()

    def ativos(self) -> int:
        return sum(1 for j in self.jobs.values() if j.status == "executando")

    def plano(self, pedido: dict) -> dict:
        if pedido.get("fluxo") == "cli":
            from .web import preview

            return {"comando": "cli", **preview(_texto(pedido.get("texto"), "a tarefa"), pedido.get("politica") or None)}
        argv = montar_comando(pedido, so_plano=True)
        r = subprocess.run(argv, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60, check=False)
        if r.returncode != 0:
            raise ValueError(_ultima_linha_de_erro(r.stderr.decode("utf-8", errors="replace")))
        return json.loads(r.stdout.decode("utf-8"))

    def iniciar(self, pedido: dict) -> Job:
        with self._lock:
            if self.ativos() >= self.maximo:
                raise ValueError(f"Já há {self.maximo} execuções em andamento; aguarde uma terminar.")
            job_id = str(uuid.uuid4())
            pasta = pasta_estado() / "jobs"
            pasta.mkdir(mode=0o700, parents=True, exist_ok=True)
            resumo = pasta / f"{job_id}.json"
            argv = montar_comando(pedido, resumo=resumo)
            titulo = (pedido.get("texto") or f"{pedido['fluxo']} {pedido.get('base') or ''}").strip()[:120]
            job = Job(job_id, pedido["fluxo"], titulo, argv, resumo=resumo)
            env = {k: v for k, v in os.environ.items() if k != "ORCHESTRATOR_PAINEL_TOKEN"}
            job.processo = subprocess.Popen(argv, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                            stderr=subprocess.PIPE, start_new_session=True, env=env)
            self.jobs[job_id] = job
        threading.Thread(target=self._acompanhar, args=(job,), daemon=True).start()
        return job

    def _acompanhar(self, job: Job) -> None:
        from .api.segredos import redigir

        def ler_erro():
            for linha in job.processo.stderr:
                texto = redigir(linha.decode("utf-8", errors="replace").rstrip())
                if texto and not texto.startswith(("WARNING", "INFO", "DEBUG")):
                    job.log.append(texto[:500])

        t = threading.Thread(target=ler_erro, daemon=True)
        t.start()
        saida = job.processo.stdout.read().decode("utf-8", errors="replace")
        job.codigo = job.processo.wait()
        t.join(timeout=2)
        job.saida = redigir(saida)
        job.fim = time.monotonic()
        job._ler_resumo()
        if job.status == "cancelado":
            return
        if job.codigo == 0:
            job.status = "ok"
        elif job.resumo and job.resumo.is_file():
            job.status = "interrompido"
        else:
            job.status = "erro"
        try:
            if job.resumo:
                job.resumo.unlink(missing_ok=True)
        except OSError:
            pass

    def cancelar(self, job_id: str) -> Job:
        job = self.obter(job_id)
        if job.status == "executando" and job.processo:
            job.status = "cancelado"
            try:
                os.killpg(job.processo.pid, signal.SIGINT)  # o CLI registra o cancelamento
                job.processo.wait(timeout=10)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                try:
                    os.killpg(job.processo.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        return job

    def obter(self, job_id: str) -> Job:
        job = self.jobs.get(job_id)
        if job is None:
            raise KeyError("Execução não encontrada.")
        return job

    def lista(self) -> list[dict]:
        return [j.as_dict() for j in sorted(self.jobs.values(), key=lambda j: j.started_at, reverse=True)]


def rodar_cli(argumentos: list[str], timeout: int = 120) -> tuple[int, str]:
    """Comandos curtos e síncronos (aplicar patch, repetir ação)."""
    r = subprocess.run([sys.executable, "-m", "orchestrator", *argumentos], cwd=ROOT, stdin=subprocess.DEVNULL,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, check=False)
    from .api.segredos import redigir

    return r.returncode, redigir(r.stdout.decode("utf-8", errors="replace"))[-8000:]


def _ultima_linha_de_erro(texto: str) -> str:
    linhas = [l for l in texto.splitlines() if l.strip() and not l.startswith(("WARNING", "INFO"))]
    erro = next((l for l in reversed(linhas) if l.startswith("Erro:")), linhas[-1] if linhas else "Falha ao montar o plano.")
    return erro.removeprefix("Erro: ")[:400]


# ------------------------------ repositórios ------------------------------

def _git(repo: Path, *args: str) -> str | None:
    r = subprocess.run(["git", *args], cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=10,
                       check=False, env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0"})
    return r.stdout.decode("utf-8", errors="replace").strip() if r.returncode == 0 else None


def info_repositorio(caminho: str) -> dict:
    repo = validar_repositorio(caminho)
    raiz = _git(repo, "rev-parse", "--show-toplevel")
    if raiz is None:
        return {"caminho": str(repo), "git": False}
    branches = (_git(repo, "for-each-ref", "--format=%(refname:short)", "--sort=-committerdate", "refs/heads", "refs/remotes") or "").splitlines()
    status = _git(repo, "status", "--porcelain=v1") or ""
    ultimo = _git(repo, "log", "-1", "--format=%h %s (%cr)") or ""
    return {"caminho": str(repo), "git": True, "raiz": raiz, "na_raiz": Path(raiz).resolve() == repo,
            "branch": _git(repo, "branch", "--show-current"), "branches": [b for b in branches if b and not b.endswith("/HEAD")][:80],
            "limpo": not status, "alteracoes": len(status.splitlines()), "ultimo_commit": ultimo[:200]}


def _arquivo_favoritos() -> Path:
    return pasta_estado() / "repositorios.json"


def favoritos() -> list[str]:
    try:
        dados = json.loads(_arquivo_favoritos().read_text(encoding="utf-8"))
        return [d for d in dados if isinstance(d, str)][:30]
    except (OSError, json.JSONDecodeError):
        return []


def salvar_favoritos(lista: list[str]) -> list[str]:
    limpos = []
    for c in lista[:30]:
        p = str(validar_repositorio(c))
        if p not in limpos:
            limpos.append(p)
    caminho = _arquivo_favoritos()
    caminho.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(caminho, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(limpos, f, ensure_ascii=False, indent=1)
    return limpos

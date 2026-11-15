"""Ações executadas quando um fluxo termina, com o nível de aprovação de cada uma.

Ações locais (salvar, notificar) são automáticas. Ações com efeito externo (comentar em PR, gravar
na biblioteca MCP) só acontecem com aprovação explícita: digitando SIM depois de ver o texto, ou
nomeando a ação em `--aprovar-acoes`. O texto enviado é conferido por SHA-256 contra o aprovado.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable
from urllib.parse import quote

from .segredos import redigir

EXTERNAS = {"comentar_pr_azure", "comentar_pr_github", "salvar_na_biblioteca"}
LOCAIS = {"notificar"}
TODAS = EXTERNAS | LOCAIS
MAX_TEXTO = 60_000


@dataclass
class Pedido:
    acao: str
    alvo: dict  # parâmetros da ação (pr, repositório, projeto MCP...)


def sha(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def interpretar(especificacoes: list[str]) -> list[Pedido]:
    """`acao` ou `acao:chave=valor,chave=valor` (ex.: comentar_pr_azure:org=x,projeto=y,repo=z,pr=12)."""
    pedidos = []
    for esp in especificacoes:
        nome, _, resto = esp.partition(":")
        if nome not in TODAS:
            raise ValueError(f"Ação desconhecida: {nome}. Disponíveis: {', '.join(sorted(TODAS))}.")
        alvo = {}
        for par in filter(None, resto.split(",")):
            k, sep, v = par.partition("=")
            if not sep or not re.fullmatch(r"[a-z_]{1,20}", k) or not v.strip():
                raise ValueError(f"Parâmetro inválido em {esp}.")
            alvo[k] = v.strip()
        pedidos.append(Pedido(nome, alvo))
    return pedidos


def _exigir(alvo: dict, *chaves: str) -> None:
    faltando = [k for k in chaves if not alvo.get(k)]
    if faltando:
        raise ValueError(f"Faltam parâmetros: {', '.join(faltando)}.")


def _post_json(url: str, corpo: dict, cabecalhos: dict) -> int:
    req = urllib.request.Request(url, data=json.dumps(corpo).encode("utf-8"), method="POST",
                                 headers={"Content-Type": "application/json", **cabecalhos})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Serviço respondeu HTTP {exc.code}.") from None
    except urllib.error.URLError as exc:
        raise RuntimeError("Falha de conexão com o serviço.") from exc


# ------------------------------ executores ------------------------------

def notificar(texto: str, alvo: dict) -> str:
    resumo = re.sub(r"[\"\\]", "", texto.splitlines()[0] if texto else "")[:120]
    if platform.system() == "Darwin":
        subprocess.run(["osascript", "-e", f'display notification "{resumo}" with title "Orquestrador"'],
                       check=False, timeout=10, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return "notificação exibida"
    print(f"\a[Orquestrador] {resumo}", file=sys.stderr)
    return "aviso no terminal"


def comentar_pr_azure(texto: str, alvo: dict) -> str:
    _exigir(alvo, "org", "projeto", "repo", "pr")
    if not alvo["pr"].isdigit():
        raise ValueError("pr deve ser numérico.")
    pat = os.environ.get("AZURE_DEVOPS_PAT", "")
    if not pat:
        raise ValueError("Defina AZURE_DEVOPS_PAT no ambiente.")
    url = (f"https://dev.azure.com/{quote(alvo['org'])}/{quote(alvo['projeto'])}/_apis/git/repositories/"
           f"{quote(alvo['repo'])}/pullRequests/{alvo['pr']}/threads?api-version=7.1")
    auth = base64.b64encode(f":{pat}".encode()).decode()
    _post_json(url, {"comments": [{"parentCommentId": 0, "content": texto, "commentType": 1}], "status": 1},
               {"Authorization": f"Basic {auth}"})
    return f"comentário publicado na PR {alvo['pr']}"


def comentar_pr_github(texto: str, alvo: dict) -> str:
    _exigir(alvo, "repo", "pr")
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", alvo["repo"]) or not alvo["pr"].isdigit():
        raise ValueError("Use repo=dono/nome e pr numérico.")
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        raise ValueError("Defina GITHUB_TOKEN no ambiente.")
    _post_json(f"https://api.github.com/repos/{alvo['repo']}/issues/{alvo['pr']}/comments", {"body": texto},
               {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"})
    return f"comentário publicado na PR #{alvo['pr']}"


def salvar_na_biblioteca(texto: str, alvo: dict) -> str:
    _exigir(alvo, "titulo", "projeto")
    from .. import mcp_prompts

    item = mcp_prompts.save(alvo["titulo"], texto, alvo["projeto"], alvo.get("tipo", "documentacao"),
                            [t for t in alvo.get("tags", "orquestrador").split("+") if t])
    return f"salvo na biblioteca como {item}"


EXECUTORES: dict[str, Callable[[str, dict], str]] = {
    "notificar": notificar, "comentar_pr_azure": comentar_pr_azure,
    "comentar_pr_github": comentar_pr_github, "salvar_na_biblioteca": salvar_na_biblioteca,
}


# ------------------------------ aprovação ------------------------------

def aprovar(pedido: Pedido, texto: str, aprovadas: set[str], entrada=input, saida=sys.stderr) -> str | None:
    """Devolve o hash aprovado, ou None se não aprovado. Ações locais não pedem aprovação."""
    if pedido.acao in LOCAIS:
        return sha(texto)
    if pedido.acao in aprovadas:
        return sha(texto)
    if not sys.stdin.isatty() and entrada is input:
        return None
    print(f"\n=== Ação {pedido.acao} {pedido.alvo} ===\n{texto[:4000]}"
          + ("\n... (texto truncado na prévia)" if len(texto) > 4000 else "")
          + f"\nSHA-256: {sha(texto)}\nDigite SIM para executar esta ação: ", file=saida, end="", flush=True)
    try:
        return sha(texto) if entrada().strip() == "SIM" else None
    except EOFError:
        return None


def executar(pedidos: list[Pedido], texto: str, aprovadas: set[str], entrada=input) -> list[dict]:
    texto = redigir(texto)[:MAX_TEXTO]
    resultados = []
    for p in pedidos:
        aprovado = aprovar(p, texto, aprovadas, entrada)
        if aprovado is None:
            resultados.append({"acao": p.acao, "status": "pendente", "detalhe": "sem aprovação; repita com orchestrator acao"})
            continue
        if aprovado != sha(texto):  # o texto mudou entre a aprovação e o envio
            resultados.append({"acao": p.acao, "status": "recusada", "detalhe": "texto diferente do aprovado"})
            continue
        try:
            resultados.append({"acao": p.acao, "status": "ok", "detalhe": EXECUTORES[p.acao](texto, p.alvo)})
        except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as exc:
            resultados.append({"acao": p.acao, "status": "erro", "detalhe": str(exc)[:300]})
    return resultados

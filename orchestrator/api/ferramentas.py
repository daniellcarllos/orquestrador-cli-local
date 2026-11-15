"""Ferramentas dadas aos agentes, limitadas a um repositório. Nenhum agente recebe shell livre.

Todas as leituras passam pela redação de segredos e respeitam limites de tamanho. Caminhos fora
do repositório, arquivos sensíveis, binários e links simbólicos são recusados.
"""

from __future__ import annotations

import fnmatch
import os
import shlex
import subprocess
from pathlib import Path

from ..changes import allowed
from .segredos import redigir

MAX_ARQUIVO = 200_000
MAX_LISTA = 500
MAX_BUSCA = 200
MAX_DIFF = 400_000
SENSIVEIS = ("*.pem", "*.key", "*.pfx", "*.p12", "id_rsa*", "*.keystore", "secrets.*", "*.secret*", "appsettings.*.json")
IGNORADOS = {".git", "node_modules", ".venv", "venv", "__pycache__", "bin", "obj", "dist", "build", ".idea", ".vs"}


class AcessoNegado(ValueError):
    pass


class Repositorio:
    def __init__(self, raiz: Path):
        self.raiz = Path(raiz).resolve(strict=True)
        if not self.raiz.is_dir():
            raise ValueError("O repositório deve ser um diretório.")

    # ---------- validação ----------
    def _caminho(self, relativo: str) -> Path:
        rel = Path(relativo.strip().lstrip("/")) if relativo.strip() not in ("", ".") else Path(".")
        if rel != Path(".") and not allowed(rel):
            raise AcessoNegado(f"Caminho não permitido: {relativo}")
        alvo = (self.raiz / rel)
        if any(p.is_symlink() for p in [alvo, *alvo.parents] if p.is_relative_to(self.raiz) and p != self.raiz):
            raise AcessoNegado("Links simbólicos não são seguidos.")
        alvo = alvo.resolve()
        if not alvo.is_relative_to(self.raiz):
            raise AcessoNegado("Caminho fora do repositório.")
        if alvo.is_file() and any(fnmatch.fnmatch(alvo.name, p) for p in SENSIVEIS):
            raise AcessoNegado(f"Arquivo sensível não é lido: {alvo.name}")
        return alvo

    def _visivel(self, p: Path) -> bool:
        rel = p.relative_to(self.raiz)
        return (not any(parte in IGNORADOS for parte in rel.parts) and allowed(rel)
                and not any(fnmatch.fnmatch(p.name, s) for s in SENSIVEIS) and not p.is_symlink())

    # ---------- ferramentas expostas aos agentes ----------
    def listar_arquivos(self, pasta: str = ".", padrao: str = "*") -> str:
        """Lista arquivos do repositório (recursivo) sob `pasta` cujo nome casa com `padrao` (ex.: *.cs)."""
        base = self._caminho(pasta)
        if not base.is_dir():
            raise AcessoNegado("Pasta inexistente.")
        saida = []
        for atual, dirs, arquivos in os.walk(base):
            dirs[:] = sorted(d for d in dirs if d not in IGNORADOS and not d.startswith(".env"))
            for nome in sorted(arquivos):
                p = Path(atual) / nome
                if fnmatch.fnmatch(nome, padrao) and self._visivel(p):
                    saida.append(str(p.relative_to(self.raiz)))
                    if len(saida) >= MAX_LISTA:
                        return "\n".join(saida) + f"\n... (limite de {MAX_LISTA} arquivos)"
        return "\n".join(saida) or "(nenhum arquivo)"

    def ler_arquivo(self, caminho: str, linha_inicial: int = 1, linha_final: int = 0) -> str:
        """Lê um arquivo de texto do repositório, opcionalmente só um intervalo de linhas (numeradas)."""
        alvo = self._caminho(caminho)
        if not alvo.is_file():
            raise AcessoNegado("Arquivo inexistente.")
        dados = alvo.read_bytes()[: MAX_ARQUIVO + 1]
        if b"\0" in dados[:8000]:
            raise AcessoNegado("Arquivo binário não é lido.")
        texto = dados[:MAX_ARQUIVO].decode("utf-8", errors="replace")
        linhas = texto.splitlines()
        ini = max(1, linha_inicial)
        fim = len(linhas) if linha_final <= 0 else min(len(linhas), linha_final)
        corpo = "\n".join(f"{i:>5}| {linhas[i - 1]}" for i in range(ini, fim + 1))
        if len(dados) > MAX_ARQUIVO:
            corpo += "\n... (arquivo truncado)"
        return redigir(corpo)

    def buscar_texto(self, termo: str, padrao: str = "*") -> str:
        """Procura um termo literal (sem regex) nos arquivos de texto; devolve arquivo:linha: trecho."""
        if not termo.strip() or len(termo) > 200:
            raise ValueError("Termo de busca inválido.")
        achados = []
        for rel in self.listar_arquivos(".", padrao).splitlines():
            if rel.startswith("..."):
                break
            p = self.raiz / rel
            try:
                dados = p.read_bytes()[:MAX_ARQUIVO]
            except OSError:
                continue
            if b"\0" in dados[:8000]:
                continue
            for n, linha in enumerate(dados.decode("utf-8", errors="replace").splitlines(), 1):
                if termo.casefold() in linha.casefold():
                    achados.append(f"{rel}:{n}: {linha.strip()[:200]}")
                    if len(achados) >= MAX_BUSCA:
                        return redigir("\n".join(achados) + "\n... (limite de resultados)")
        return redigir("\n".join(achados) or "(nenhum resultado)")

    # ---------- usados pelo orquestrador (não pelos modelos) ----------
    def git_diff(self, base: str, head: str = "HEAD") -> str:
        for ref in (base, head):
            if not ref or ref.startswith("-") or any(c in ref for c in " \t\n;|&$`"):
                raise ValueError("Referência git inválida.")
        r = subprocess.run(["git", "diff", "--no-ext-diff", "--no-color", f"{base}...{head}", "--"],
                           cwd=self.raiz, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
                           env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
        if r.returncode:
            raise ValueError("git diff falhou: " + r.stderr.decode(errors="replace").strip()[:300])
        if len(r.stdout) > MAX_DIFF:
            raise ValueError("Diff grande demais para revisão; divida por pasta ou commit.")
        return filtrar_diff(r.stdout.decode("utf-8", errors="replace"))


def filtrar_diff(diff: str) -> str:
    """Remove do diff blocos de arquivos sensíveis e redige segredos no restante."""
    blocos, atual, manter = [], [], True
    for linha in diff.splitlines(keepends=True):
        if linha.startswith("diff --git "):
            if atual and manter:
                blocos.append("".join(atual))
            atual = [linha]
            caminho = linha.split(" b/", 1)[-1].strip()
            nome = Path(caminho).name
            manter = allowed(Path(caminho)) and not any(fnmatch.fnmatch(nome, p) for p in SENSIVEIS)
        else:
            atual.append(linha)
    if atual and manter:
        blocos.append("".join(atual))
    return redigir("".join(blocos))


def dividir_diff(diff: str) -> dict[str, str]:
    """Separa o diff por arquivo: {caminho: trecho}."""
    partes: dict[str, list[str]] = {}
    atual = None
    for linha in diff.splitlines(keepends=True):
        if linha.startswith("diff --git "):
            atual = linha.split(" b/", 1)[-1].strip()
            partes[atual] = []
        if atual:
            partes[atual].append(linha)
    return {k: "".join(v) for k, v in partes.items()}


def rodar_testes(pasta: Path, comando: str, permitidos: list[str], timeout: int = 600) -> dict:
    """Executa um comando de teste da lista branca do projeto, sem shell. Usado pelo orquestrador."""
    if comando not in permitidos:
        raise AcessoNegado("Comando de teste fora da lista permitida.")
    argv = shlex.split(comando)
    try:
        r = subprocess.run(argv, cwd=pasta, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, check=False)
        saida = r.stdout.decode("utf-8", errors="replace")
        return {"comando": comando, "codigo": r.returncode, "ok": r.returncode == 0, "saida": redigir(saida[-20_000:])}
    except subprocess.TimeoutExpired:
        return {"comando": comando, "codigo": None, "ok": False, "saida": "tempo esgotado"}
    except OSError as exc:
        return {"comando": comando, "codigo": None, "ok": False, "saida": f"falha ao executar: {exc.strerror}"}

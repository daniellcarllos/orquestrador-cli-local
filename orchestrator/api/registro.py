"""Pasta privada por execução e linha-resumo no histórico compartilhado com o painel."""

from __future__ import annotations

import json
import os
import shutil
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..cli import history_path, journal
from .segredos import redigir

RETENCAO_DIAS = 30


def pasta_execucoes() -> Path:
    return history_path().parent / "execucoes"


def _escrever_privado(caminho: Path, texto: str) -> None:
    fd = os.open(caminho, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(texto)


@dataclass
class Etapa:
    papel: str
    nivel: str
    provedor: str
    modelo: str
    status: str = "pendente"  # pendente | ok | fora_do_contrato | erro | cancelada | teto
    tokens_entrada: int = 0
    tokens_saida: int = 0
    custo_usd: float | None = None
    duracao_ms: int = 0
    rodada: int = 1
    detalhe: str | None = None


@dataclass
class Execucao:
    fluxo: str
    tarefa_resumo: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))
    etapas: list[Etapa] = field(default_factory=list)
    acoes: list[dict] = field(default_factory=list)
    status: str = "executando"
    progresso_ativo: bool = False  # grava meta.json a cada etapa (acompanhamento ao vivo pelo painel)
    _inicio: float = field(default_factory=time.monotonic, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @property
    def pasta(self) -> Path:
        p = pasta_execucoes() / self.id
        p.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(p.parent, 0o700)
        return p

    def adicionar(self, etapa: Etapa) -> Etapa:
        with self._lock:
            self.etapas.append(etapa)
        self.progresso()
        return etapa

    def progresso(self) -> None:
        if self.progresso_ativo:
            with self._lock:
                meta = self.meta()
            self.salvar("meta.json", meta)

    def salvar(self, nome: str, conteudo: str | dict | list) -> Path:
        texto = conteudo if isinstance(conteudo, str) else json.dumps(conteudo, ensure_ascii=False, indent=2)
        caminho = self.pasta / nome
        _escrever_privado(caminho, redigir(texto))
        return caminho

    def meta(self, orcamento: dict | None = None) -> dict:
        return {
            "id": self.id, "action": self.fluxo, "modo": "api", "started_at": self.started_at,
            "status": self.status, "duration_ms": round((time.monotonic() - self._inicio) * 1000),
            "tarefa": self.tarefa_resumo[:120],
            "etapas": [asdict(e) for e in self.etapas], "acoes": self.acoes,
            **(orcamento or {}),
        }

    def finalizar(self, status: str, orcamento: dict | None = None) -> dict:
        self.status = status
        meta = self.meta(orcamento)
        self.salvar("meta.json", meta)
        # Linha do histórico: só metadados, compatível com o painel.
        agentes = sorted({e.provedor for e in self.etapas})
        journal({**{k: meta[k] for k in ("id", "action", "modo", "started_at", "status", "duration_ms")},
                 "agent": "api", "provedores": agentes, "policy_version": "api-1",
                 "model": ",".join(sorted({e.modelo for e in self.etapas})) or None, "usage": None,
                 "exit_code": 0 if status == "ok" else 1, "timed_out": False, "truncated": False,
                 "custo_usd": meta.get("custo_usd"), "tokens": meta.get("tokens"),
                 "etapas": [{k: v for k, v in asdict(e).items() if k != "detalhe"} for e in self.etapas]})
        return meta


def limpar(dias: int = RETENCAO_DIAS, agora: datetime | None = None) -> int:
    """Remove pastas de execução mais antigas que `dias`. Devolve quantas removeu."""
    base = pasta_execucoes()
    if not base.is_dir():
        return 0
    limite = (agora or datetime.now(timezone.utc)) - timedelta(days=dias)
    removidas = 0
    for p in base.iterdir():
        if p.is_dir() and not p.is_symlink() and datetime.fromtimestamp(p.stat().st_mtime, timezone.utc) < limite:
            shutil.rmtree(p)
            removidas += 1
    return removidas


def ler(execucao_id: str) -> dict:
    try:
        uuid.UUID(execucao_id)
    except ValueError as exc:
        raise ValueError("Id de execução inválido.") from exc
    caminho = pasta_execucoes() / execucao_id / "meta.json"
    if not caminho.is_file():
        raise ValueError("Execução não encontrada.")
    return json.loads(caminho.read_text(encoding="utf-8"))

"""Preço por token, estimativa antes de executar e teto de gasto por execução e por dia."""

from __future__ import annotations

import threading
from datetime import datetime, timezone

CARACTERES_POR_TOKEN = 4  # aproximação conservadora para estimativa prévia


class TetoExcedido(RuntimeError):
    """Gasto real ou estimado passou do teto autorizado."""


def preco(catalogo: dict, modelo: str) -> tuple[float, float] | None:
    p = catalogo.get("precos_por_milhao", {}).get(modelo)
    if not p or p["entrada"] is None or p["saida"] is None:
        return None
    return float(p["entrada"]), float(p["saida"])


def custo(tokens_entrada: int, tokens_saida: int, preco_modelo: tuple[float, float] | None) -> float | None:
    if preco_modelo is None:
        return None
    return round(tokens_entrada / 1_000_000 * preco_modelo[0] + tokens_saida / 1_000_000 * preco_modelo[1], 6)


def tokens_estimados(texto: str) -> int:
    return len(texto) // CARACTERES_POR_TOKEN + 1


def estimar(catalogo: dict, modelo: str, texto_entrada: str, tokens_saida_max: int = 4000) -> float | None:
    return custo(tokens_estimados(texto_entrada), tokens_saida_max, preco(catalogo, modelo))


class Orcamento:
    """Acumula o gasto de uma execução (todas as etapas e agentes) e barra o que passar do teto.

    Modelos sem preço configurado contam tokens, mas não custo: o teto em dólares não os limita,
    então o limite de tokens (`teto_tokens`) é a proteção nesse caso.
    """

    def __init__(self, teto_usd: float | None, teto_tokens: int | None = None, gasto_dia_usd: float = 0.0,
                 teto_dia_usd: float | None = None):
        if teto_usd is not None and teto_usd <= 0:
            raise ValueError("O teto por execução deve ser positivo.")
        self.teto_usd = teto_usd
        self.teto_tokens = teto_tokens
        self.teto_dia_usd = teto_dia_usd
        self.gasto_dia_usd = gasto_dia_usd
        self.usd = 0.0
        self.tokens = 0
        self.sem_preco: set[str] = set()
        self._lock = threading.Lock()

    def verificar(self, estimativa_usd: float | None = None, estimativa_tokens: int = 0) -> None:
        with self._lock:
            extra = estimativa_usd or 0.0
            if self.teto_usd is not None and self.usd + extra > self.teto_usd:
                raise TetoExcedido(f"Teto por execução de US$ {self.teto_usd:.2f} atingido (gasto US$ {self.usd:.4f}, próxima etapa estimada em US$ {extra:.4f}).")
            if self.teto_dia_usd is not None and self.gasto_dia_usd + self.usd + extra > self.teto_dia_usd:
                raise TetoExcedido(f"Teto diário de US$ {self.teto_dia_usd:.2f} atingido.")
            if self.teto_tokens is not None and self.tokens + estimativa_tokens > self.teto_tokens:
                raise TetoExcedido(f"Teto de {self.teto_tokens} tokens atingido.")

    def registrar(self, modelo: str, tokens: int, usd: float | None) -> None:
        with self._lock:
            self.tokens += tokens
            if usd is None:
                self.sem_preco.add(modelo)
            else:
                self.usd = round(self.usd + usd, 6)

    def resumo(self) -> dict:
        return {"custo_usd": round(self.usd, 6), "tokens": self.tokens, "teto_usd": self.teto_usd,
                "modelos_sem_preco": sorted(self.sem_preco)}


def gasto_do_dia(entradas: list[dict], agora: datetime | None = None) -> float:
    """Soma o custo das execuções de API registradas hoje (UTC)."""
    hoje = (agora or datetime.now(timezone.utc)).date().isoformat()
    return round(sum(e.get("custo_usd") or 0.0 for e in entradas
                     if e.get("modo") == "api" and str(e.get("started_at", "")).startswith(hoje)), 6)

"""Catálogo de modelos por nível (leve, médio, forte) e escolha pelo provedor configurado."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

NIVEIS = ("leve", "medio", "forte")
PROVEDORES = {"anthropic": "ANTHROPIC_API_KEY", "google": "GOOGLE_API_KEY", "openai": "OPENAI_API_KEY"}
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}")
CATALOGO_PADRAO = Path(__file__).resolve().parents[2] / "examples" / "api" / "modelos.json"


@dataclass(frozen=True)
class Escolha:
    nivel: str
    provedor: str
    modelo: str

    def as_dict(self) -> dict:
        return {"nivel": self.nivel, "provedor": self.provedor, "modelo": self.modelo}


def _candidato(item, onde: str) -> dict:
    if not isinstance(item, dict) or set(item) != {"provedor", "modelo"}:
        raise ValueError(f"Catálogo: {onde} deve ter exatamente provedor e modelo.")
    if item["provedor"] not in PROVEDORES:
        raise ValueError(f"Catálogo: provedor desconhecido em {onde}.")
    if not isinstance(item["modelo"], str) or not _ID.fullmatch(item["modelo"]):
        raise ValueError(f"Catálogo: identificador de modelo inválido em {onde}.")
    return item


def validar(data) -> dict:
    if not isinstance(data, dict) or not isinstance(data.get("versao"), str):
        raise ValueError("Catálogo inválido: informe versao.")
    niveis = data.get("niveis")
    if not isinstance(niveis, dict) or set(niveis) != set(NIVEIS):
        raise ValueError("Catálogo deve definir os níveis leve, medio e forte.")
    for nivel, item in niveis.items():
        _candidato(item, nivel)
    alternativos = data.get("alternativos", {})
    if not isinstance(alternativos, dict) or not set(alternativos) <= set(NIVEIS):
        raise ValueError("Catálogo: alternativos inválidos.")
    for nivel, lista in alternativos.items():
        if not isinstance(lista, list):
            raise ValueError("Catálogo: alternativos devem ser listas.")
        for i, item in enumerate(lista):
            _candidato(item, f"alternativos.{nivel}[{i}]")
    precos = data.get("precos_por_milhao", {})
    if not isinstance(precos, dict):
        raise ValueError("Catálogo: precos_por_milhao inválido.")
    for modelo, preco in precos.items():
        if not isinstance(preco, dict) or set(preco) != {"entrada", "saida"}:
            raise ValueError(f"Catálogo: preço de {modelo} deve ter entrada e saida.")
        for v in preco.values():
            if v is not None and (not isinstance(v, (int, float)) or v < 0):
                raise ValueError(f"Catálogo: preço inválido para {modelo}.")
    return data


def carregar(caminho: Path | None = None) -> dict:
    caminho = caminho or CATALOGO_PADRAO
    try:
        data = json.loads(Path(caminho).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Não foi possível ler o catálogo de modelos: {exc}") from exc
    return validar(data)


def provedores_configurados(env=None) -> dict[str, bool]:
    env = os.environ if env is None else env
    return {p: bool(env.get(var, "").strip()) for p, var in PROVEDORES.items()}


def escolher(catalogo: dict, nivel: str, env=None, *, simulado: bool = False) -> Escolha:
    """Primeiro candidato do nível cujo provedor tem chave; no modo simulado, sempre o principal."""
    if nivel not in NIVEIS:
        raise ValueError("Nível de modelo desconhecido.")
    candidatos = [catalogo["niveis"][nivel], *catalogo.get("alternativos", {}).get(nivel, [])]
    if simulado:
        c = candidatos[0]
        return Escolha(nivel, c["provedor"], c["modelo"])
    configurados = provedores_configurados(env)
    for c in candidatos:
        if configurados[c["provedor"]]:
            return Escolha(nivel, c["provedor"], c["modelo"])
    faltando = sorted({PROVEDORES[c["provedor"]] for c in candidatos})
    raise ValueError(f"Nenhum provedor configurado para o nível {nivel}: defina {' ou '.join(faltando)}.")


def criar_modelo(escolha: Escolha, simulado=None, *, papel: str = "", esquema=None):
    """Instancia o modelo Agno. `simulado` (um ModeloSimulado) substitui a chamada real."""
    if simulado is not None:
        return simulado.para(escolha, papel, esquema)
    if escolha.provedor == "anthropic":
        from agno.models.anthropic import Claude

        return Claude(id=escolha.modelo)
    if escolha.provedor == "google":
        from agno.models.google import Gemini

        return Gemini(id=escolha.modelo)
    if escolha.provedor == "openai":
        from agno.models.openai import OpenAIChat

        return OpenAIChat(id=escolha.modelo)
    raise ValueError("Provedor desconhecido.")

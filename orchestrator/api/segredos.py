"""Redação de segredos em textos enviados aos modelos, logs e resultados."""

from __future__ import annotations

import re

from ..terminal.core import redact as _redigir_basico

_PADROES = [
    (re.compile(r"sk-ant-[A-Za-z0-9_\-]{10,}"), "[CHAVE-ANTHROPIC]"),
    (re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_\-]{20,}"), "[CHAVE-OPENAI]"),
    (re.compile(r"\bAIza[0-9A-Za-z_\-]{30,}"), "[CHAVE-GOOGLE]"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}"), "[TOKEN-GITHUB]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[CHAVE-AWS]"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S), "[CHAVE-PRIVADA]"),
    (re.compile(r"(?i)\b(password|senha|pwd)\s*=\s*[^;\s\"']+"), r"\1=[REDIGIDO]"),
    (re.compile(r"(?i)(connection\s*string|connectionstring)\s*[:=]\s*\S+"), r"\1=[REDIGIDO]"),
]


def redigir(texto: str) -> str:
    texto = _redigir_basico(texto)
    for padrao, troca in _PADROES:
        texto = padrao.sub(troca, texto)
    return texto

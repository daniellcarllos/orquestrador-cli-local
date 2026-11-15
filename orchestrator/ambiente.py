"""Carrega variáveis de um arquivo .env (chaves de API e configurações) sem dependências.

Regras:
- variáveis já definidas no ambiente têm prioridade (o .env nunca sobrescreve);
- arquivo padrão: `.env` na raiz do projeto; outro caminho via ORCHESTRATOR_ENV_FILE;
- só nomes em MAIÚSCULAS, formato `NOME=valor` (aceita `export`, aspas e comentários);
- se o arquivo puder ser lido por outros usuários, avisa para usar `chmod 600`;
- valores nunca são impressos.
"""

from __future__ import annotations

import os
import re
import stat
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
_LINHA = re.compile(r"^\s*(?:export\s+)?([A-Z][A-Z0-9_]{0,63})\s*=\s*(.*?)\s*$")


def arquivo_env() -> Path:
    return Path(os.environ.get("ORCHESTRATOR_ENV_FILE") or RAIZ / ".env").expanduser()


def interpretar(texto: str) -> dict[str, str]:
    valores: dict[str, str] = {}
    for linha in texto.splitlines():
        if not linha.strip() or linha.lstrip().startswith("#"):
            continue
        m = _LINHA.match(linha)
        if not m:
            continue
        nome, valor = m.groups()
        if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "\"'":
            valor = valor[1:-1]
        else:
            valor = re.split(r"\s+#", valor, maxsplit=1)[0].strip()  # comentário no fim da linha
        valores[nome] = valor
    return valores


def carregar(caminho: Path | None = None, ambiente=None, avisos=sys.stderr) -> list[str]:
    """Carrega o .env no ambiente. Devolve os nomes aplicados (nunca os valores)."""
    caminho = caminho or arquivo_env()
    ambiente = os.environ if ambiente is None else ambiente
    try:
        info = caminho.lstat()
    except FileNotFoundError:
        return []
    if not stat.S_ISREG(info.st_mode):
        print(f"Aviso: {caminho} não é um arquivo comum; ignorado.", file=avisos)
        return []
    if info.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        print(f"Aviso: {caminho} pode ser lido por outros usuários. Rode: chmod 600 {caminho}", file=avisos)
    aplicados = []
    for nome, valor in interpretar(caminho.read_text(encoding="utf-8")).items():
        if valor and not ambiente.get(nome):
            ambiente[nome] = valor
            aplicados.append(nome)
    return aplicados

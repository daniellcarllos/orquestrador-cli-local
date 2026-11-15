"""Consulta local e optativa de versões e opções documentadas pela própria CLI."""

from __future__ import annotations

import re
from pathlib import Path

from .core import execute


def inspect(agent: str, executable: str, cwd: Path) -> dict:
    try:
        version = execute([executable, "--version"], "", cwd, 10)
        help_cmd = [executable, "exec", "--help"] if agent == "codex" else [executable, "--help"]
        help_result = execute(help_cmd, "", cwd, 10)
    except OSError:
        return {"agent": agent, "version": None, "help_available": False, "model_flag": None,
                "json_flag": None, "sandbox_flag": None, "session_flag": None,
                "token_usage": "não verificado", "authentication": "não verificada",
                "note": "Não foi possível executar os comandos locais de diagnóstico."}
    version_match = re.search(r"\b\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.]+)?\b", version.stdout)
    ok = help_result.exit_code == 0 and not help_result.timed_out and not help_result.truncated
    help_text = help_result.stdout if ok else ""
    return {
        "agent": agent,
        "version": version_match.group(0) if version.exit_code == 0 and version_match else None,
        "help_available": ok,
        "model_flag": "--model" in help_text if ok else None,
        "json_flag": ("--json" in help_text or "--output-format" in help_text) if ok else None,
        "sandbox_flag": "--sandbox" in help_text if ok else None,
        "session_flag": "--resume" in help_text or "resume  " in help_text if ok else None,
        "token_usage": "não verificado",
        "authentication": "não verificada",
        "note": "Opções declaradas na ajuda; não confirma modelos, autenticação, permissões ou consumo.",
    }

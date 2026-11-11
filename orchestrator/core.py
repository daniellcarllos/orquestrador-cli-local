"""Política determinística e execução restrita de uma única CLI."""

from __future__ import annotations

import os
import re
import shutil
import signal
import subprocess
import threading
from dataclasses import asdict, dataclass
from pathlib import Path

AGENTS = ("codex", "claude", "gemini")
OUTPUT_LIMIT = 1024 * 1024
POLICY_VERSION = "1"


@dataclass(frozen=True)
class Plan:
    agent: str
    complexity: str
    risk: str
    policy_version: str
    rationale: str
    scope: str

    def as_dict(self) -> dict:
        return asdict(self)


def detect() -> dict[str, str | None]:
    return {agent: shutil.which(agent) for agent in AGENTS}


def plan(task: str, available: dict[str, str | None], agent: str | None = None) -> Plan:
    if not task.strip():
        raise ValueError("A tarefa não pode estar vazia.")
    if agent and (agent not in AGENTS or not available.get(agent)):
        raise ValueError("Agente solicitado indisponível.")
    selected = agent or next((name for name in AGENTS if available.get(name)), None)
    if not selected:
        raise ValueError("Nenhuma CLI elegível encontrada no PATH.")
    text = task.casefold()
    high = any(x in text for x in ("segurança", "security", "deploy", "produção", "production", "credencial", "secret", "excluir", "delete"))
    medium = any(x in text for x in ("código", "codigo", "code", "teste", "test", "analis", "review", "revis"))
    return Plan(selected, "alta" if high else "média" if medium else "simples", "alto" if high else "baixo", POLICY_VERSION,
                "agente escolhido pelo usuário" if agent else "primeiro agente disponível na ordem configurada", "somente leitura pretendida; isolamento específico da CLI não é garantia universal")


def command(agent: str, executable: str, cwd: Path) -> list[str]:
    if agent == "codex":
        return [executable, "exec", "--sandbox", "read-only", "--ephemeral", "--cd", str(cwd), "-"]
    if agent == "claude":
        return [executable, "--print", "--restricted", "--tools", "", "--no-session-persistence"]
    if agent == "gemini":
        return [executable, "--prompt", "", "--approval-mode", "plan"]
    raise ValueError("Agente desconhecido.")


def redact(text: str) -> str:
    text = re.sub(r"(?i)(authorization\s*:\s*bearer\s+)\S+", r"\1[REDACTED]", text)
    text = re.sub(r"(?i)((?:api[_-]?key|access[_-]?token|password|secret)\s*[:=]\s*)[^\s,;]+", r"\1[REDACTED]", text)
    return text


@dataclass
class Result:
    exit_code: int | None
    stdout: str
    stderr: str
    timed_out: bool
    truncated: bool


def execute(argv: list[str], task: str, cwd: Path, timeout: int) -> Result:
    if timeout < 1 or timeout > 3600:
        raise ValueError("Timeout deve estar entre 1 e 3600 segundos.")
    process = subprocess.Popen(argv, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               start_new_session=True, shell=False)
    outputs: list[bytearray] = [bytearray(), bytearray()]
    truncated = [False]

    def read(stream, target):
        while True:
            chunk = stream.read(8192)
            if not chunk:
                break
            remaining = max(0, OUTPUT_LIMIT - len(target))
            target.extend(chunk[:remaining])
            if len(chunk) > remaining:
                truncated[0] = True
        stream.close()

    threads = [threading.Thread(target=read, args=(stream, buf), daemon=True)
               for stream, buf in zip((process.stdout, process.stderr), outputs)]
    for thread in threads:
        thread.start()

    def send_input():
        try:
            process.stdin.write(task.encode("utf-8"))
            process.stdin.close()
        except (BrokenPipeError, OSError):
            pass

    writer = threading.Thread(target=send_input, daemon=True)
    writer.start()
    timed_out = False
    try:
        process.wait(timeout=timeout)
    except (subprocess.TimeoutExpired, KeyboardInterrupt) as exc:
        timed_out = isinstance(exc, subprocess.TimeoutExpired)
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()
        if not timed_out:
            raise
    for thread in threads:
        thread.join(timeout=2)
    return Result(process.returncode, *(redact(x.decode("utf-8", errors="replace")) for x in outputs), timed_out, truncated[0])

"""Política determinística e execução restrita de uma única CLI."""

from __future__ import annotations

import os
import json
import re
import shutil
import signal
import subprocess
import threading
from dataclasses import asdict, dataclass
from pathlib import Path

AGENTS = ("codex", "claude", "gemini")
OUTPUT_LIMIT = 1024 * 1024
POLICY_VERSION = "2"


@dataclass(frozen=True)
class Plan:
    agent: str
    complexity: str
    risk: str
    policy_version: str
    rationale: str
    scope: str
    model: str | None = None
    task_type: str = "geral"
    routing_mode: str = "compatibilidade"
    usage: str = "desconhecido"

    def as_dict(self) -> dict:
        return asdict(self)


def detect() -> dict[str, str | None]:
    return {agent: shutil.which(agent) for agent in AGENTS}


def load_policy(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Não foi possível ler a política: {exc}") from exc
    if not isinstance(data, dict) or set(data) != {"version", "tiers"} or not isinstance(data["version"], str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,40}", data["version"]):
        raise ValueError("Política inválida: esperados version e tiers.")
    tiers = data["tiers"]
    if not isinstance(tiers, dict) or set(tiers) != {"simples", "média", "alta"}:
        raise ValueError("Política deve definir os níveis simples, média e alta.")
    for candidates in tiers.values():
        if not isinstance(candidates, list) or not candidates:
            raise ValueError("Cada nível deve ter pelo menos um candidato autorizado.")
        for candidate in candidates:
            if not isinstance(candidate, dict) or set(candidate) != {"agent", "model"} or candidate["agent"] not in AGENTS:
                raise ValueError("Candidato inválido: informe agent e model.")
            model = candidate["model"]
            if model is not None and (not isinstance(model, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}", model)):
                raise ValueError("Identificador de modelo inválido.")
    return data


def classify(task: str) -> tuple[str, str, str]:
    text = task.casefold()
    risky = any(x in text for x in ("segurança", "security", "deploy", "produção", "production", "credencial", "secret", "excluir", "delete"))
    planning = any(x in text for x in ("planej", "planea", "planeamento", "plano", "planning", "architecture", "arquitetura"))
    review = any(x in text for x in ("review", "revis", "confer", "verific", "validar", "validação", "validation"))
    medium = any(x in text for x in ("código", "codigo", "code", "teste", "test", "analis", "implementar", "implement"))
    category = "segurança" if risky else "planejamento" if planning else "conferência" if review else "código" if medium else "geral"
    return ("alta" if risky or planning or review else "média" if medium or len(task) > 2000 else "simples", "alto" if risky else "baixo", category)


def plan(task: str, available: dict[str, str | None], agent: str | None = None, policy: dict | None = None) -> Plan:
    if not task.strip():
        raise ValueError("A tarefa não pode estar vazia.")
    if agent and (agent not in AGENTS or not available.get(agent)):
        raise ValueError("Agente solicitado indisponível.")
    complexity, risk, category = classify(task)
    candidates = policy["tiers"][complexity] if policy else [{"agent": name, "model": None} for name in AGENTS]
    selected = next((item for item in candidates if (agent is None or item["agent"] == agent) and available.get(item["agent"])), None)
    if not selected:
        raise ValueError("Nenhum agente autorizado pela política está disponível para este nível.")
    reason = "primeiro candidato disponível no nível da política" if policy else "ordem padrão de compatibilidade; sem otimização comprovada"
    return Plan(selected["agent"], complexity, risk, policy["version"] if policy else POLICY_VERSION,
                reason, "isolamento e política de dados dependem da CLI e do ambiente", selected["model"], category,
                "configurada" if policy else "compatibilidade")


def command(agent: str, executable: str, cwd: Path, *, write: bool = False, model: str | None = None) -> list[str]:
    model_args = ["--model", model] if model else []
    if agent == "codex":
        return [executable, "exec", "--sandbox", "workspace-write" if write else "read-only", "--ephemeral", "--cd", str(cwd), *model_args, "-"]
    if agent == "claude" and write:
        return [executable, "--print", "--restricted", "--strict-mcp-config", "--tools", "Read,Edit,Write,Glob,Grep",
                "--permission-mode", "acceptEdits", "--permission-prompts", "none", "--no-session-persistence", *model_args]
    if write:
        raise ValueError("Este agente não suporta a preparação de alterações.")
    if agent == "claude":
        return [executable, "--print", "--restricted", "--tools", "", "--no-session-persistence", *model_args]
    if agent == "gemini":
        return [executable, "--prompt", "", "--approval-mode", "plan", *model_args]
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
    env = {k: v for k, v in os.environ.items() if k != "MCP_PROMPTS_TOKEN"}
    process = subprocess.Popen(argv, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               start_new_session=True, shell=False, env=env)
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

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
import uuid
from pathlib import Path

from .core import AGENTS, command, detect, execute, plan


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="orchestrator", description="Orquestrador local em modo single")
    commands = p.add_subparsers(dest="action", required=True)
    commands.add_parser("doctor", help="Detectar CLIs no PATH sem invocá-las")
    for name in ("plan", "run"):
        sub = commands.add_parser(name)
        sub.add_argument("task")
        sub.add_argument("--agent", choices=AGENTS)
        sub.add_argument("--cwd", type=Path, default=Path.cwd())
        if name == "run":
            sub.add_argument("--mode", choices=("single",), default="single")
            sub.add_argument("--approve", action="store_true", help="Aprovar a execução e o eventual consumo de cota")
            sub.add_argument("--timeout", type=int, default=300)
    commands.add_parser("history", help="Histórico local de metadados, sem prompts ou saídas")
    return p


def history_path() -> Path:
    return Path(os.environ.get("ORCHESTRATOR_STATE_DIR", Path.home() / ".local" / "state" / "orquestrador-cli-local")) / "history.jsonl"


def journal(entry: dict) -> None:
    path = history_path()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    if args.action == "doctor":
        print(json.dumps({"platform": platform.system(), "python": platform.python_version(),
                          "agents": {k: bool(v) for k, v in detect().items()},
                          "note": "Disponibilidade no PATH; versão e autenticação não verificadas."}, ensure_ascii=False, indent=2))
        return 0
    if args.action == "history":
        path = history_path()
        if path.exists():
            print(path.read_text(encoding="utf-8"), end="")
        return 0
    try:
        cwd = args.cwd.resolve(strict=True)
        if not cwd.is_dir():
            raise ValueError("O diretório de trabalho não é um diretório.")
        available = detect()
        selected = plan(args.task, available, args.agent)
        print(json.dumps({**selected.as_dict(), "cwd": str(cwd)}, ensure_ascii=False, indent=2), flush=True)
        if args.action == "plan":
            return 0
        if not args.approve:
            print("Execução não iniciada: use --approve após revisar o plano e o escopo.", file=sys.stderr)
            return 2
        if args.timeout < 1 or args.timeout > 3600:
            raise ValueError("Timeout deve estar entre 1 e 3600 segundos.")
        run_id = str(uuid.uuid4())
        start = time.monotonic()
        result = execute(command(selected.agent, available[selected.agent], cwd), args.task, cwd, args.timeout)
        journal({"id": run_id, "agent": selected.agent, "policy_version": selected.policy_version,
                 "duration_ms": round((time.monotonic() - start) * 1000), "exit_code": result.exit_code,
                 "timed_out": result.timed_out, "truncated": result.truncated})
        print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, file=sys.stderr, end="")
        print("\nResultado do processo registrado; sucesso funcional requer validação independente.", file=sys.stderr)
        if result.truncated:
            print("Saída truncada.", file=sys.stderr)
        return 124 if result.timed_out else (result.exit_code if result.exit_code is not None and result.exit_code >= 0 else 1)
    except (ValueError, OSError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

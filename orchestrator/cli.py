from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
import uuid
from pathlib import Path

from . import capabilities, changes, mcp_prompts
from .core import AGENTS, command, detect, execute, load_policy, plan


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="orchestrator", description="Orquestrador local em modo single")
    commands = p.add_subparsers(dest="action", required=True)
    doctor = commands.add_parser("doctor", help="Detectar CLIs e opcionalmente consultar suas ajudas")
    doctor.add_argument("--probe", action="store_true", help="Executar comandos locais de versão e ajuda")
    for name in ("plan", "run"):
        sub = commands.add_parser(name)
        sub.add_argument("task")
        sub.add_argument("--agent", choices=AGENTS)
        sub.add_argument("--policy", type=Path, help="Arquivo JSON de roteamento autorizado")
        sub.add_argument("--cwd", type=Path, default=Path.cwd())
        if name == "run":
            sub.add_argument("--mode", choices=("single",), default="single")
            sub.add_argument("--approve", action="store_true", help="Aprovar a execução e o eventual consumo de cota")
            sub.add_argument("--timeout", type=int, default=300)
            sub.add_argument("--mcp-prompt-id", help="ID da referência de revisão no MCP")
            sub.add_argument("--mcp-context-id", action="append", default=[], help="ID de contexto adicional (opcional)")
            sub.add_argument("--mcp-context-tag", help="Selecionar contextos recentes com esta tag exata")
            sub.add_argument("--mcp-max-contexts", type=int, default=2, help="Limite de documentos obtidos pela tag (1 a 4)")
            sub.add_argument("--mcp-project", help="Projeto esperado para todos os documentos")
            sub.add_argument("--mcp-group", help="Grupo esperado para todos os documentos")
            sub.add_argument("--approve-mcp", action="store_true", help="Autorizar leitura dos IDs informados no MCP")
            sub.add_argument("--input-file", type=Path, help="Diff ou texto local autorizado para revisão")
    commands.add_parser("history", help="Histórico local de metadados, sem prompts ou saídas")
    listing = commands.add_parser("mcp-list", help="Listar metadados MCP por projeto, grupo e tag opcional")
    listing.add_argument("--project", required=True)
    listing.add_argument("--group", required=True)
    listing.add_argument("--tag")
    listing.add_argument("--approve-mcp", action="store_true")
    prepare = commands.add_parser("prepare", help="Preparar patch em cópia temporária")
    prepare.add_argument("task")
    prepare.add_argument("--agent", choices=("codex", "claude"))
    prepare.add_argument("--policy", type=Path, help="Arquivo JSON de roteamento autorizado")
    prepare.add_argument("--cwd", type=Path, default=Path.cwd())
    prepare.add_argument("--output", type=Path, required=True, help="Novo diretório para a proposta")
    prepare.add_argument("--timeout", type=int, default=300)
    prepare.add_argument("--approve", action="store_true", help="Autorizar execução em cópia e consumo de cota")
    apply = commands.add_parser("apply", help="Aplicar patch revisado a repositório limpo")
    apply.add_argument("proposal", type=Path)
    apply.add_argument("--cwd", type=Path, default=Path.cwd())
    apply.add_argument("--approve-sha256", required=True, help="Hash SHA-256 do patch revisado")
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
        found = detect()
        inventory = {k: capabilities.inspect(k, v, Path.cwd()) if v and args.probe else {"available": bool(v)} for k, v in found.items()}
        print(json.dumps({"platform": platform.system(), "python": platform.python_version(),
                          "agents": inventory,
                          "note": "Autenticação, elegibilidade de modelos e consumo de tokens não foram verificados."}, ensure_ascii=False, indent=2))
        return 0
    if args.action == "history":
        path = history_path()
        if path.exists():
            print(path.read_text(encoding="utf-8"), end="")
        return 0
    if args.action == "mcp-list":
        try:
            if not args.approve_mcp:
                raise ValueError("A listagem remota requer --approve-mcp.")
            entries = mcp_prompts.list_metadata(args.project, args.group, args.tag)
            print(json.dumps({"count": len(entries), "prompts": entries}, ensure_ascii=False, indent=2))
            return 0
        except (ValueError, OSError) as exc:
            print(f"Erro: {exc}", file=sys.stderr)
            return 2
    try:
        cwd = args.cwd.resolve(strict=True)
        if not cwd.is_dir():
            raise ValueError("O diretório de trabalho não é um diretório.")
        if args.action == "apply":
            changes.apply(cwd, args.proposal.resolve(strict=True), args.approve_sha256)
            print("Patch aplicado. Revise o diff e execute os testes apropriados.")
            return 0
        if args.action == "prepare":
            if not args.task.strip():
                raise ValueError("A tarefa não pode estar vazia.")
            available = detect()
            available["gemini"] = None  # escrita ainda não suportada
            selected = plan(args.task, available, args.agent, load_policy(args.policy) if args.policy else None)
            print(json.dumps({**selected.as_dict(), "source": str(cwd), "proposal": str(args.output.resolve()),
                              "scope": "cópia temporária de arquivos rastreados; proposta fora da origem",
                              "effects": "execução da CLI e possível consumo de cota; isolamento depende da CLI"},
                             ensure_ascii=False, indent=2), flush=True)
            if not args.approve:
                raise ValueError("Preparação não iniciada: a execução requer --approve.")
            if not 1 <= args.timeout <= 3600:
                raise ValueError("Timeout deve estar entre 1 e 3600 segundos.")
            executable = available[selected.agent]
            if selected.model and capabilities.inspect(selected.agent, executable, cwd)["model_flag"] is not True:
                raise ValueError("Seleção de modelo não confirmada pela ajuda da CLI; execução bloqueada.")
            output = args.output.resolve()
            if output.exists() or output.is_relative_to(cwd):
                raise ValueError("A proposta deve ser um diretório novo fora da origem.")
            base = changes.validate_source(cwd)
            with changes.temporary_copy() as tmp:
                copy = Path(tmp)
                changes.copy_tracked(cwd, copy)
                if changes.validate_source(cwd) != base:
                    raise ValueError("A origem mudou durante a cópia.")
                changes.init_copy(copy)
                result = execute(command(selected.agent, executable, copy, write=True, model=selected.model), args.task, copy, args.timeout)
                if result.timed_out or result.exit_code != 0:
                    raise ValueError("Execução falhou ou expirou; nenhuma proposta foi criada.")
                metadata = changes.export_patch(copy, output, base)
            print(json.dumps({"proposal": str(output), **metadata}, ensure_ascii=False, indent=2))
            print("Revise changes.patch antes de autorizar sua aplicação.")
            return 0
        available = detect()
        selected = plan(args.task, available, args.agent, load_policy(args.policy) if args.policy else None)
        mcp_ids = ([args.mcp_prompt_id, *args.mcp_context_id] if args.action == "run" and args.mcp_prompt_id else [])
        if args.action == "run" and (args.mcp_context_id or args.mcp_context_tag or args.mcp_project or args.mcp_group or args.approve_mcp or args.input_file) and not args.mcp_prompt_id:
            raise ValueError("Para revisão MCP, informe --mcp-prompt-id.")
        print(json.dumps({**selected.as_dict(), "cwd": str(cwd), **({"mcp_ids": mcp_ids, "mcp_context_tag": args.mcp_context_tag} if mcp_ids else {})}, ensure_ascii=False, indent=2), flush=True)
        if args.action == "plan":
            return 0
        if not args.approve:
            print("Execução não iniciada: use --approve após revisar o plano e o escopo.", file=sys.stderr)
            return 2
        if args.timeout < 1 or args.timeout > 3600:
            raise ValueError("Timeout deve estar entre 1 e 3600 segundos.")
        if selected.model and capabilities.inspect(selected.agent, available[selected.agent], cwd)["model_flag"] is not True:
            raise ValueError("Seleção de modelo não confirmada pela ajuda da CLI; execução bloqueada.")
        task = args.task
        if mcp_ids:
            if not args.approve_mcp or not args.mcp_project or not args.mcp_group:
                raise ValueError("A leitura MCP exige --approve-mcp, --mcp-project e --mcp-group.")
            if not 1 <= args.mcp_max_contexts <= 4:
                raise ValueError("O limite de contextos por tag deve estar entre 1 e 4.")
            if not args.input_file:
                raise ValueError("A revisão exige --input-file com diff ou conteúdo autorizado.")
            source = args.input_file.resolve(strict=True)
            if not source.is_file() or source.stat().st_size > 200_000:
                raise ValueError("O arquivo de revisão deve ser um arquivo de até 200 KB.")
            try:
                review_input = source.read_text(encoding="utf-8")
            except UnicodeError as exc:
                raise ValueError("O arquivo de revisão deve usar UTF-8.") from exc
            tagged_ids = []
            if args.mcp_context_tag:
                entries = mcp_prompts.list_metadata(args.mcp_project, args.mcp_group, args.mcp_context_tag)
                candidates = [entry for entry in entries if entry["id"] not in mcp_ids]
                if not candidates:
                    raise ValueError("Nenhum contexto adicional encontrado para a tag no projeto e grupo informados.")
                tagged_ids = [entry["id"] for entry in candidates[:args.mcp_max_contexts]]
                if len(mcp_ids) + len(tagged_ids) > 5:
                    raise ValueError("O total de documentos selecionados excede cinco.")
                print(json.dumps({"matched_contexts": len(candidates), "selected_contexts": candidates[:args.mcp_max_contexts]}, ensure_ascii=False), flush=True)
            docs = mcp_prompts.fetch([*mcp_ids, *tagged_ids], args.mcp_project, args.mcp_group)
            for doc in docs:
                if doc["id"] in tagged_ids and not any(isinstance(tag, str) and tag.casefold() == args.mcp_context_tag.casefold() for tag in doc.get("tags", [])):
                    raise ValueError("A tag do contexto selecionado mudou desde a listagem.")
            print(json.dumps({"mcp_documentos": [{k: doc.get(k) for k in ("id", "title", "version", "updated_at")} for doc in docs]}, ensure_ascii=False), flush=True)
            task = mcp_prompts.build_review_task(args.task, review_input, docs)
        run_id = str(uuid.uuid4())
        start = time.monotonic()
        result = execute(command(selected.agent, available[selected.agent], cwd, model=selected.model), task, cwd, args.timeout)
        journal({"id": run_id, "agent": selected.agent, "policy_version": selected.policy_version,
                 "model": selected.model, "usage": None, "duration_ms": round((time.monotonic() - start) * 1000), "exit_code": result.exit_code,
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

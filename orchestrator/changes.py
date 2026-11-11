"""Prepara patches em uma cópia descartável, sem modificar o projeto de origem."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path

MAX_FILE = 5 * 1024 * 1024
MAX_TOTAL = 50 * 1024 * 1024
MAX_PATCH = 10 * 1024 * 1024
BLOCKED_NAMES = {".git", ".ssh", ".aws", ".env", "node_modules", ".venv", "venv", "__pycache__"}


def git(cwd: Path, *args: str, input_data: bytes | None = None) -> bytes:
    env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0"}
    result = subprocess.run(["git", *args], cwd=cwd, env=env, input=input_data,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode:
        raise ValueError("Comando Git falhou: " + result.stderr.decode(errors="replace").strip())
    return result.stdout


def allowed(path: Path) -> bool:
    return not path.is_absolute() and bool(path.parts) and all(
        part not in BLOCKED_NAMES and not part.startswith(".env.") and part not in (".", "..")
        for part in path.parts
    )


def validate_source(source: Path) -> str:
    root = Path(os.fsdecode(git(source, "rev-parse", "--show-toplevel").strip())).resolve()
    if root != source.resolve():
        raise ValueError("Informe a raiz de um repositório Git.")
    if git(root, "status", "--porcelain=v1", "--untracked-files=all"):
        raise ValueError("O repositório de origem deve estar limpo, incluindo arquivos não rastreados.")
    return git(root, "rev-parse", "HEAD").decode().strip()


def copy_tracked(source: Path, target: Path) -> None:
    names = git(source, "ls-files", "-z").split(b"\0")
    total = 0
    for raw in names:
        if not raw:
            continue
        relative = Path(os.fsdecode(raw))
        if not allowed(relative):
            continue
        original = source / relative
        # Verifica cada componente: nem links nem submódulos são copiados.
        for parent in [*relative.parents][:-1]:
            if (source / parent).is_symlink():
                raise ValueError("Links simbólicos no projeto não são suportados.")
        info = original.lstat()
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("A cópia aceita apenas arquivos regulares, sem links ou submódulos.")
        total += info.st_size
        if info.st_size > MAX_FILE or total > MAX_TOTAL:
            raise ValueError("O projeto excede o limite de tamanho da cópia.")
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original, destination, follow_symlinks=False)


def init_copy(copy: Path) -> None:
    git(copy, "init", "-q")
    git(copy, "-c", "core.hooksPath=/dev/null", "add", "--all")
    git(copy, "-c", "user.name=Orchestrator", "-c", "user.email=local@invalid",
        "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", "commit", "-qm", "Snapshot", "--allow-empty")


def export_patch(copy: Path, destination: Path, commit: str) -> dict:
    # Rejeita links antes de adicionar arquivos, inclusive novos e caminhos sensíveis.
    changes = git(copy, "status", "--porcelain=v1", "-z", "--untracked-files=all", "--no-renames")
    if len(changes) > MAX_PATCH:
        raise ValueError("Lista de alterações excede o limite.")
    for raw in changes.split(b"\0"):
        if not raw:
            continue
        path = Path(os.fsdecode(raw[3:]))
        if not allowed(path):
            raise ValueError("A proposta contém um caminho não permitido.")
        candidate = copy / path
        if candidate.is_symlink() or any((copy / parent).is_symlink() for parent in list(path.parents)[:-1]):
            raise ValueError("A proposta contém link simbólico.")
        if candidate.exists() and (not candidate.is_file() or candidate.stat().st_size > MAX_FILE):
            raise ValueError("Arquivo proposto inválido ou grande demais.")
    git(copy, "-c", "core.hooksPath=/dev/null", "add", "--all")
    patch = git(copy, "diff", "--cached", "--binary", "--no-ext-diff", "--no-renames", "--")
    if len(patch) > MAX_PATCH:
        raise ValueError("Patch excede o limite.")
    if not patch:
        raise ValueError("A execução não produziu alterações.")
    destination.mkdir(parents=True, exist_ok=False, mode=0o700)
    patch_path = destination / "changes.patch"
    patch_path.write_bytes(patch)
    os.chmod(patch_path, 0o600)
    metadata = {"base_commit": commit, "patch_sha256": hashlib.sha256(patch).hexdigest(), "bytes": len(patch)}
    manifest = destination / "manifest.json"
    manifest.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    os.chmod(manifest, 0o600)
    return metadata


def apply(source: Path, proposal: Path, approved_sha256: str) -> None:
    base = validate_source(source)
    manifest = json.loads((proposal / "manifest.json").read_text(encoding="utf-8"))
    patch = (proposal / "changes.patch").read_bytes()
    digest = hashlib.sha256(patch).hexdigest()
    if len(patch) > MAX_PATCH or digest != manifest["patch_sha256"] or digest != approved_sha256:
        raise ValueError("Patch modificado ou inválido.")
    if base != manifest["base_commit"]:
        raise ValueError("Commit de origem mudou desde a preparação.")
    # Não aceitar links, submódulos ou alterações de caminhos sensíveis, mesmo
    # se o arquivo de proposta tiver sido alterado depois da sua geração.
    if b"mode 120000" in patch or b"mode 160000" in patch:
        raise ValueError("Patch com link simbólico ou submódulo não é permitido.")
    entries = git(source, "apply", "--numstat", "-z", "--", "-", input_data=patch).split(b"\0")
    for entry in entries:
        if entry:
            fields = entry.split(b"\t", 2)
            if len(fields) != 3 or not allowed(Path(os.fsdecode(fields[2]))):
                raise ValueError("Patch contém caminho não permitido.")
    git(source, "apply", "--check", "--", "-", input_data=patch)
    git(source, "apply", "--", "-", input_data=patch)


def temporary_copy():
    return tempfile.TemporaryDirectory(prefix="orchestrator-")

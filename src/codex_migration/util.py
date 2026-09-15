from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import platform
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .errors import MigrationError


EXCLUDED_BASENAMES = {
    "auth.json",
    "login data",
    "cookies",
    "cookies-journal",
    "lock",
    "singletonlock",
}
EXCLUDED_SUFFIXES = {"-wal", "-shm", ".lock", ".pid", ".tmp"}
EXCLUDED_PARTS = {"cache", "code cache", "gpu cache", "temp", "tmp", "crashpad"}
KNOWN_APP_NAMES = {
    "chatgpt.exe",
    "codex.exe",
    "codex-code-mode-host.exe",
    "codex-command-runner.exe",
    "chatgpt",
    "codex",
    "codex-code-mode-host",
    "codex-command-runner",
}


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def relative_posix(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def is_excluded(relative_path: Path) -> bool:
    lowered_parts = [part.lower() for part in relative_path.parts]
    filename = relative_path.name.lower()
    if filename in EXCLUDED_BASENAMES or filename.endswith(".sqlite-wal") or filename.endswith(".sqlite-shm"):
        return True
    if any(filename.endswith(suffix) for suffix in EXCLUDED_SUFFIXES):
        return True
    return any(part in EXCLUDED_PARTS for part in lowered_parts)


def copy_tree(source: Path, destination: Path, *, exclude_portable: bool = False) -> dict[str, int]:
    """Copy a tree with metadata, returning copied/skipped file counts."""
    copied = 0
    skipped = 0
    for source_path in source.rglob("*"):
        relative = source_path.relative_to(source)
        if exclude_portable and is_excluded(relative):
            skipped += 1
            continue
        destination_path = destination / relative
        if source_path.is_dir():
            destination_path.mkdir(parents=True, exist_ok=True)
        elif source_path.is_file():
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, destination_path)
            copied += 1
    return {"copied_files": copied, "skipped_entries": skipped}


def iter_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if path.is_file():
            yield path


def ensure_empty_or_missing(directory: Path) -> None:
    if directory.exists() and any(directory.iterdir()):
        raise MigrationError(f"Destination must be absent or empty: {directory}")


def known_running_processes() -> list[str]:
    """Best-effort process detection with no third-party dependency."""
    try:
        if os.name == "nt":
            completed = subprocess.run(
                ["tasklist", "/FO", "CSV", "/NH"], check=True, capture_output=True, text=True
            )
            rows = csv.reader(io.StringIO(completed.stdout))
            names = {row[0].lower() for row in rows if row and row[0] != "INFO: No tasks are running"}
        else:
            completed = subprocess.run(["ps", "-axo", "comm="], check=True, capture_output=True, text=True)
            names = {Path(line.strip()).name.lower() for line in completed.stdout.splitlines() if line.strip()}
    except (OSError, subprocess.CalledProcessError):
        return []
    return sorted(name for name in names if name in KNOWN_APP_NAMES)


def require_apps_stopped() -> None:
    running = known_running_processes()
    if running:
        raise MigrationError(
            "Codex/ChatGPT appears to be running (" + ", ".join(running) + "). "
            "Fully quit desktop and CLI processes, including the tray process, then retry."
        )


def host_metadata() -> dict[str, str]:
    return {
        "os": platform.system(),
        "os_release": platform.release(),
        "python": platform.python_version(),
    }

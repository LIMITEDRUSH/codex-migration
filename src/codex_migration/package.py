from __future__ import annotations

import json
from pathlib import Path

from .errors import MigrationError
from .inventory import inspect_codex_home
from .manifest import verify_manifest, write_manifest
from .util import copy_tree, ensure_empty_or_missing, host_metadata, require_apps_stopped, utc_timestamp, write_json


def parse_project(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise MigrationError(f"Project must be NAME=PATH, received: {value!r}")
    name, raw_path = (part.strip() for part in value.split("=", 1))
    if not name or not raw_path or any(character in name for character in "\\/:"):
        raise MigrationError(f"Project name must be a simple directory name, received: {value!r}")
    path = Path(raw_path).expanduser()
    if not path.is_dir():
        raise MigrationError(f"Project directory does not exist: {path}")
    return name, path


def export_package(codex_home: Path, output: Path, projects: list[tuple[str, Path]]) -> dict[str, object]:
    codex_home = codex_home.expanduser()
    output = output.expanduser()
    if not codex_home.is_dir():
        raise MigrationError(f"Codex home is not a directory: {codex_home}")
    require_apps_stopped()
    ensure_empty_or_missing(output)
    output.mkdir(parents=True, exist_ok=True)
    codex_summary = copy_tree(codex_home, output / "codex-home", exclude_portable=True)
    project_summary: dict[str, object] = {}
    for name, project_path in projects:
        project_summary[name] = {"source": str(project_path), **copy_tree(project_path, output / "projects" / name)}
    package_metadata = {
        "schema": 1,
        "created_at": utc_timestamp(),
        "source": host_metadata(),
        "portable_profile": "codex-home",
        "excluded": "auth, browser credentials, locks, WAL/SHM, and cache/runtime paths",
        "projects": sorted(project_summary),
    }
    write_json(output / "package.json", package_metadata)
    inventory = inspect_codex_home(codex_home)
    write_json(output / "reports" / "source-inventory.json", inventory)
    manifest_entries = write_manifest(output)
    verification = verify_manifest(output)
    if not verification["ok"]:
        raise MigrationError("Package manifest verification failed immediately after export")
    return {
        "package": str(output),
        "manifest_entries": manifest_entries,
        "codex": codex_summary,
        "projects": project_summary,
        "source_inventory": inventory,
    }

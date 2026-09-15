from __future__ import annotations

import tarfile
import json
import os
import platform
import shutil
from pathlib import Path

from .errors import MigrationError
from .inventory import inspect_codex_home
from .manifest import verify_manifest, write_manifest
from .util import (
    copy_tree,
    ensure_empty_or_missing,
    host_metadata,
    is_excluded,
    require_apps_stopped,
    require_free_space,
    utc_timestamp,
    write_json,
)


ARCHIVE_TRANSPORT = "archive"
DIRECTORY_TRANSPORT = "directory"
SUPPORTED_TRANSPORTS = {ARCHIVE_TRANSPORT, DIRECTORY_TRANSPORT}

_RUNTIME_LAUNCHER = '''"""Run the bundled Codex Migration toolkit without installing it."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codex_migration.cli import main  # noqa: E402

raise SystemExit(main())
'''

_WINDOWS_RESTORE = r'''param(
    [Parameter(Mandatory = $true)]
    [string]$PackageRoot
)

$ErrorActionPreference = 'Stop'
$PackageRoot = (Resolve-Path -LiteralPath $PackageRoot).Path
$Runner = Join-Path $PackageRoot 'toolkit\scripts\codex-migration.py'
if (-not (Test-Path -LiteralPath $Runner)) {
    throw "The bundled recovery toolkit is missing: $Runner"
}
if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 $Runner one-click-restore --package $PackageRoot
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python $Runner one-click-restore --package $PackageRoot
} else {
    throw 'Python 3.10 or newer is required. Install Python, then run this file again.'
}
exit $LASTEXITCODE
'''

_WINDOWS_RESTORE_CMD = r'''@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\toolkit\scripts\Restore-From-USB.ps1" -PackageRoot "%~dp0.."
set "CODE=%ERRORLEVEL%"
if not "%CODE%"=="0" pause
exit /b %CODE%
'''

_MAC_RESTORE = r'''#!/bin/bash
set -u
ROOT="$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)"
RUNNER="$ROOT/toolkit/scripts/codex-migration.py"
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3.10 or newer is required. Install Python 3, then run this file again."
  read -r -p "Press Return to close..." _
  exit 2
fi
exec python3 "$RUNNER" one-click-restore --package "$ROOT"
'''


def _embed_recovery_toolkit(output: Path) -> dict[str, str]:
    """Put a dependency-free copy of this runtime and double-click launchers in each package."""
    toolkit = output / "toolkit"
    module_source = Path(__file__).resolve().parent
    for source in module_source.rglob("*.py"):
        relative = source.relative_to(module_source)
        destination = toolkit / "src" / "codex_migration" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    runner = toolkit / "scripts" / "codex-migration.py"
    runner.parent.mkdir(parents=True, exist_ok=True)
    runner.write_text(_RUNTIME_LAUNCHER, encoding="utf-8", newline="\n")
    restore_ps1 = toolkit / "scripts" / "Restore-From-USB.ps1"
    restore_ps1.write_text(_WINDOWS_RESTORE, encoding="utf-8", newline="\r\n")

    launchers = output / "launcher"
    launchers.mkdir(parents=True, exist_ok=True)
    (launchers / "RESTORE-WINDOWS.cmd").write_text(_WINDOWS_RESTORE_CMD, encoding="utf-8", newline="\r\n")
    mac_launcher = launchers / "RESTORE-MAC.command"
    mac_launcher.write_text(_MAC_RESTORE, encoding="utf-8", newline="\n")
    mac_launcher.chmod(0o755)
    (launchers / "README.txt").write_text(
        "Windows: double-click RESTORE-WINDOWS.cmd after installing Codex and fully quitting it.\n"
        "macOS: double-click RESTORE-MAC.command after installing Codex and fully quitting it.\n"
        "The recovery tool verifies the package, backs up the target Codex home, restores projects, and maps paths.\n"
        "It cannot migrate login credentials; sign in again after recovery.\n",
        encoding="utf-8",
        newline="\n",
    )
    return {
        "windows": "launcher/RESTORE-WINDOWS.cmd",
        "macos": "launcher/RESTORE-MAC.command",
        "runtime": "toolkit/scripts/codex-migration.py",
    }


def parse_project(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise MigrationError(f"Project must be NAME=PATH, received: {value!r}")
    name, raw_path = (part.strip() for part in value.split("=", 1))
    if not name or not raw_path or any(character in name for character in "\\\\/:") or name in {".", ".."}:
        raise MigrationError(f"Project name must be a simple directory name, received: {value!r}")
    path = Path(raw_path).expanduser()
    if not path.is_dir():
        raise MigrationError(f"Project directory does not exist: {path}")
    return name, path


def discover_registered_projects(codex_home: Path) -> list[tuple[str, Path]]:
    """Return every existing root registered by Codex, failing rather than silently omitting one."""
    state_path = codex_home / ".codex-global-state.json"
    if not state_path.is_file():
        return []
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MigrationError(f"Cannot read Codex project registry {state_path}: {error}") from error
    projects = state.get("local-projects") if isinstance(state, dict) else None
    if not isinstance(projects, dict):
        return []

    discovered: list[tuple[str, Path]] = []
    missing: list[str] = []
    used_names: set[str] = set()
    seen_paths: set[Path] = set()
    for project_id, project in sorted(projects.items()):
        roots = project.get("rootPaths") if isinstance(project, dict) else None
        if not isinstance(roots, list):
            continue
        for root in roots:
            if not isinstance(root, str):
                continue
            path = Path(root).expanduser()
            if not path.is_dir():
                missing.append(f"{project_id}: {path}")
                continue
            canonical = path.resolve()
            if canonical in seen_paths:
                continue
            seen_paths.add(canonical)
            raw_name = path.name or "project"
            base = "".join(character if character.isalnum() or character in "-_" else "_" for character in raw_name)
            base = base.strip("._") or "project"
            name = base
            suffix = 2
            while name in used_names:
                name = f"{base}-{suffix}"
                suffix += 1
            used_names.add(name)
            discovered.append((name, path))
    if missing:
        raise MigrationError(
            "Codex registers project roots that are missing on this source computer; refusing to silently omit them: "
            + "; ".join(missing)
        )
    return discovered


def merge_projects(registered: list[tuple[str, Path]], additional: list[tuple[str, Path]]) -> list[tuple[str, Path]]:
    """Merge automatic and explicit roots, preferring explicit names for duplicate paths."""
    by_path: dict[Path, tuple[str, Path]] = {}
    for name, path in registered:
        by_path[path.resolve()] = (name, path)
    for name, path in additional:
        by_path[path.resolve()] = (name, path)
    merged = list(by_path.values())
    names = [name for name, _ in merged]
    if len(set(names)) != len(names):
        raise MigrationError("Two selected projects use the same package name; rename one --project entry")
    return sorted(merged, key=lambda item: item[0].lower())


def default_desktop_state_source(codex_home: Path) -> Path | None:
    """Find the one conventional desktop-state location safe to retain as an unapplied snapshot."""
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        candidate = Path(appdata) / "Codex" if appdata else None
    elif platform.system() == "Darwin":
        candidate = Path.home() / "Library" / "Application Support" / "Codex"
    else:
        candidate = Path.home() / ".config" / "Codex"
    if not candidate or not candidate.is_dir() or candidate.resolve() == codex_home.resolve():
        return None
    return candidate


def _iter_payload_paths(source: Path, *, exclude_portable: bool) -> list[Path]:
    paths: list[Path] = []
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        if exclude_portable and is_excluded(relative):
            continue
        if path.is_symlink():
            raise MigrationError(
                f"Refusing to package symbolic link {path}. Copy its intended local content into the project first."
            )
        if path.is_dir() or path.is_file():
            paths.append(path)
    return paths


def _estimated_tar_bytes(source: Path, *, exclude_portable: bool) -> int:
    # Each TAR member has a 512-byte header and is padded to 512-byte blocks.
    total = 1024
    for path in _iter_payload_paths(source, exclude_portable=exclude_portable):
        total += 512
        if path.is_file():
            total += ((path.stat().st_size + 511) // 512) * 512
    return total


def _write_tar(source: Path, destination: Path, prefix: str, *, exclude_portable: bool) -> dict[str, int]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    members = _iter_payload_paths(source, exclude_portable=exclude_portable)
    file_count = 0
    with tarfile.open(destination, mode="w", format=tarfile.PAX_FORMAT) as archive:
        for path in members:
            relative = path.relative_to(source).as_posix()
            archive.add(path, arcname=f"{prefix}/{relative}", recursive=False)
            if path.is_file():
                file_count += 1
    return {"files": file_count, "entries": len(members), "archive_bytes": destination.stat().st_size}


def _preflight_space(
    output: Path, codex_home: Path, projects: list[tuple[str, Path]], desktop_state: Path | None, transport: str
) -> None:
    inputs = [(codex_home, True), *[(path, False) for _, path in projects]]
    if desktop_state:
        inputs.append((desktop_state, True))
    required = sum(_estimated_tar_bytes(path, exclude_portable=portable) for path, portable in inputs)
    if transport == DIRECTORY_TRANSPORT:
        # A directory tree on FAT/exFAT can require far more allocation units than its file sizes suggest.
        required *= 2
    # Package metadata, manifest, and filesystem accounting leave an explicit buffer.
    require_free_space(output, required + 16 * 1024 * 1024)


def export_package(
    codex_home: Path,
    output: Path,
    projects: list[tuple[str, Path]],
    *,
    transport: str = ARCHIVE_TRANSPORT,
    desktop_state: Path | None = None,
) -> dict[str, object]:
    """Build a self-contained USB package. No cloud service is assumed or contacted."""
    codex_home = codex_home.expanduser()
    output = output.expanduser()
    if transport not in SUPPORTED_TRANSPORTS:
        raise MigrationError(f"Unsupported transport {transport!r}; choose one of {sorted(SUPPORTED_TRANSPORTS)}")
    if not codex_home.is_dir():
        raise MigrationError(f"Codex home is not a directory: {codex_home}")
    if len({name for name, _ in projects}) != len(projects):
        raise MigrationError("Two selected projects use the same package name")
    if desktop_state:
        desktop_state = desktop_state.expanduser()
        if not desktop_state.is_dir():
            raise MigrationError(f"Desktop-state directory does not exist: {desktop_state}")
    require_apps_stopped()
    ensure_empty_or_missing(output)
    _preflight_space(output, codex_home, projects, desktop_state, transport)
    output.mkdir(parents=True, exist_ok=True)

    project_summary: dict[str, object] = {}
    payloads: dict[str, object]
    if transport == ARCHIVE_TRANSPORT:
        codex_archive = output / "archives" / "codex-home.tar"
        codex_summary = _write_tar(codex_home, codex_archive, "codex-home", exclude_portable=True)
        project_payloads: dict[str, str] = {}
        for name, project_path in projects:
            archive_path = output / "archives" / "projects" / f"{name}.tar"
            project_summary[name] = {
                "source": str(project_path),
                **_write_tar(project_path, archive_path, f"projects/{name}", exclude_portable=False),
            }
            project_payloads[name] = archive_path.relative_to(output).as_posix()
        desktop_payload = None
        desktop_summary = None
        if desktop_state:
            desktop_archive = output / "archives" / "desktop-state-safety.tar"
            desktop_summary = _write_tar(desktop_state, desktop_archive, "desktop-state-safety", exclude_portable=True)
            desktop_payload = desktop_archive.relative_to(output).as_posix()
        payloads = {
            "codex_home": codex_archive.relative_to(output).as_posix(),
            "projects": project_payloads,
            "desktop_state_safety": desktop_payload,
        }
    else:
        codex_summary = copy_tree(codex_home, output / "codex-home", exclude_portable=True)
        project_payloads = {}
        for name, project_path in projects:
            project_summary[name] = {"source": str(project_path), **copy_tree(project_path, output / "projects" / name)}
            project_payloads[name] = f"projects/{name}"
        desktop_payload = None
        desktop_summary = None
        if desktop_state:
            desktop_summary = copy_tree(desktop_state, output / "desktop-state-safety", exclude_portable=True)
            desktop_payload = "desktop-state-safety"
        payloads = {"codex_home": "codex-home", "projects": project_payloads, "desktop_state_safety": desktop_payload}

    recovery_launcher = _embed_recovery_toolkit(output)
    package_metadata = {
        "schema": 3,
        "created_at": utc_timestamp(),
        "source": host_metadata(),
        "source_codex_home": str(codex_home),
        "transport": transport,
        "portable_profile": "codex-home",
        "payloads": payloads,
        "excluded": "auth, browser credentials, locks, WAL/SHM, and cache/runtime paths",
        "projects": sorted(project_summary),
        "project_sources": {name: str(path) for name, path in projects},
        "desktop_state_safety": {"source": str(desktop_state), "restore": "manual-only"} if desktop_state else None,
        "recovery_launcher": recovery_launcher,
        "cloud_assumption": "none; all included payloads are written to this package",
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
        "transport": transport,
        "manifest_entries": manifest_entries,
        "codex": codex_summary,
        "projects": project_summary,
        "desktop_state_safety": desktop_summary,
        "recovery_launcher": recovery_launcher,
        "source_inventory": inventory,
    }

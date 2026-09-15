from __future__ import annotations

import json
import os
import shutil
import sqlite3
import tarfile
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any

from .errors import MigrationError
from .inventory import inspect_codex_home
from .manifest import verify_manifest
from .mapping import PathMapping
from .rewrite import rewrite_structured_paths
from .util import copy_tree, require_apps_stopped, utc_timestamp, write_json


def _read_package_metadata(package: Path) -> dict[str, Any]:
    metadata_path = package / "package.json"
    if not metadata_path.is_file():
        raise MigrationError(f"Package metadata is missing: {metadata_path}")
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MigrationError(f"Cannot read package metadata: {error}") from error
    if not isinstance(metadata, dict):
        raise MigrationError("Package metadata must be a JSON object")
    return metadata


def _transport(metadata: dict[str, Any]) -> str:
    transport = metadata.get("transport", "directory")  # schema 1 compatibility
    if transport not in {"archive", "directory"}:
        raise MigrationError(f"Unsupported package transport: {transport!r}")
    return transport


def _relative_payload_path(value: object, description: str) -> Path:
    if not isinstance(value, str):
        raise MigrationError(f"Package metadata is missing {description}")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise MigrationError(f"Package metadata contains an unsafe {description}: {value!r}")
    return path


def _payload_path(package: Path, metadata: dict[str, Any], kind: str, project_name: str | None = None) -> Path:
    if _transport(metadata) == "directory":
        if kind == "codex":
            return package / "codex-home"
        if kind == "desktop-state-safety":
            return package / "desktop-state-safety"
        return package / f"projects/{project_name}"
    payloads = metadata.get("payloads")
    if not isinstance(payloads, dict):
        raise MigrationError("Archive package is missing payload metadata")
    value: object = payloads.get("codex_home") if kind == "codex" else None
    if kind == "desktop-state-safety":
        value = payloads.get("desktop_state_safety")
    if kind == "project":
        projects = payloads.get("projects")
        value = projects.get(project_name) if isinstance(projects, dict) else None
    return package / _relative_payload_path(value, f"payload for {kind}")


def _safe_extract_tar(archive_path: Path, destination: Path, expected_prefix: str) -> None:
    """Extract only ordinary files/dirs below one expected TAR prefix."""
    if not archive_path.is_file():
        raise MigrationError(f"Package payload is missing: {archive_path}")
    prefix = PurePosixPath(expected_prefix)
    try:
        with tarfile.open(archive_path, mode="r") as archive:
            for member in archive:
                member_path = PurePosixPath(member.name)
                if member_path.is_absolute() or ".." in member_path.parts or member_path.parts[: len(prefix.parts)] != prefix.parts:
                    raise MigrationError(f"Unsafe archive member in {archive_path.name}: {member.name!r}")
                remainder = member_path.parts[len(prefix.parts) :]
                if not remainder:
                    continue
                if member.issym() or member.islnk() or member.isdev() or member.isfifo():
                    raise MigrationError(f"Unsupported link/device member in {archive_path.name}: {member.name!r}")
                target = destination.joinpath(*remainder)
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                elif member.isfile():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    extracted = archive.extractfile(member)
                    if extracted is None:
                        raise MigrationError(f"Cannot read archive member {member.name!r}")
                    with extracted, target.open("wb") as target_file:
                        shutil.copyfileobj(extracted, target_file)
                    os.chmod(target, member.mode)
                else:
                    raise MigrationError(f"Unsupported archive member in {archive_path.name}: {member.name!r}")
    except (OSError, tarfile.TarError) as error:
        raise MigrationError(f"Cannot safely extract {archive_path}: {error}") from error


def _rewrite_json_file(path: Path, mappings: list[PathMapping]) -> int:
    try:
        original = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return 0
    rewritten, changes = rewrite_structured_paths(original, mappings)
    if changes:
        path.write_text(json.dumps(rewritten, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return changes


def _rewrite_jsonl_file(path: Path, mappings: list[PathMapping]) -> int:
    try:
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    except (OSError, UnicodeDecodeError):
        return 0
    changed = 0
    rewritten_lines: list[str] = []
    for line in lines:
        if not line.strip():
            rewritten_lines.append(line)
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            return 0
        rewritten, line_changes = rewrite_structured_paths(value, mappings)
        changed += line_changes
        ending = "\r\n" if line.endswith("\r\n") else "\n"
        rewritten_lines.append(json.dumps(rewritten, separators=(",", ":"), ensure_ascii=False) + ending)
    if changed:
        path.write_text("".join(rewritten_lines), encoding="utf-8", newline="")
    return changed


def _rewrite_sqlite(path: Path, mappings: list[PathMapping]) -> int:
    changes = 0
    connection = sqlite3.connect(path)
    try:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "threads" in tables:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(threads)")}
            for column, path_key in (("cwd", "cwd"), ("rollout_path", "rollout_path")):
                if column not in columns:
                    continue
                rows = list(connection.execute(f"SELECT rowid, {column} FROM threads WHERE {column} IS NOT NULL"))
                for rowid, raw_path in rows:
                    if not isinstance(raw_path, str):
                        continue
                    rewritten, count = rewrite_structured_paths(raw_path, mappings, key=path_key)
                    if count:
                        connection.execute(f"UPDATE threads SET {column} = ? WHERE rowid = ?", (rewritten, rowid))
                        changes += count
            for column in ("sandbox_policy", "permission_profile", "file_system_sandbox_policy"):
                if column not in columns:
                    continue
                rows = list(connection.execute(f"SELECT rowid, {column} FROM threads WHERE {column} IS NOT NULL"))
                for rowid, raw_value in rows:
                    if not isinstance(raw_value, str):
                        continue
                    try:
                        parsed = json.loads(raw_value)
                    except json.JSONDecodeError:
                        continue
                    rewritten, count = rewrite_structured_paths(parsed, mappings)
                    if count:
                        connection.execute(
                            f"UPDATE threads SET {column} = ? WHERE rowid = ?",
                            (json.dumps(rewritten, separators=(",", ":")), rowid),
                        )
                        changes += count
        if "project_roots" in tables:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(project_roots)")}
            if "path" in columns:
                rows = list(connection.execute("SELECT rowid, path FROM project_roots WHERE path IS NOT NULL"))
                for rowid, raw_path in rows:
                    if not isinstance(raw_path, str):
                        continue
                    rewritten, count = rewrite_structured_paths(raw_path, mappings, key="path")
                    if count:
                        connection.execute("UPDATE project_roots SET path = ? WHERE rowid = ?", (rewritten, rowid))
                        changes += count
        connection.commit()
        quick_check = connection.execute("PRAGMA quick_check").fetchone()[0]
        if quick_check != "ok":
            raise MigrationError(f"SQLite quick_check failed for {path}: {quick_check}")
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    return changes


def rewrite_staged_paths(stage: Path, mappings: list[PathMapping]) -> dict[str, int]:
    results = {"json": 0, "jsonl": 0, "sqlite": 0}
    if not mappings:
        return results
    for path in stage.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix == ".json":
            results["json"] += _rewrite_json_file(path, mappings)
        elif path.suffix == ".jsonl":
            results["jsonl"] += _rewrite_jsonl_file(path, mappings)
        elif path.suffix == ".sqlite":
            results["sqlite"] += _rewrite_sqlite(path, mappings)
        elif path.name == "cap_sid":
            results["json"] += _rewrite_json_file(path, mappings)
    return results


def build_restore_plan(
    package: Path, target_codex_home: Path, mappings: list[PathMapping], project_destination: Path | None = None
) -> dict[str, Any]:
    verification = verify_manifest(package)
    package_metadata = _read_package_metadata(package)
    transport = _transport(package_metadata)
    source_payload = _payload_path(package, package_metadata, "codex")
    if transport == "directory" and not source_payload.is_dir():
        raise MigrationError("Package does not contain codex-home/")
    if transport == "archive" and not source_payload.is_file():
        raise MigrationError("Package does not contain the Codex profile archive")
    inventory_path = package / "reports" / "source-inventory.json"
    try:
        source_inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MigrationError(f"Package source inventory is missing or unreadable: {error}") from error
    desktop_state_safety = package_metadata.get("desktop_state_safety")
    desktop_payload = None
    if desktop_state_safety:
        desktop_payload = _payload_path(package, package_metadata, "desktop-state-safety")
        if not desktop_payload.exists():
            raise MigrationError("Package desktop-state safety payload is missing")
    return {
        "schema": 2,
        "package": str(package),
        "target_codex_home": str(target_codex_home),
        "manifest": verification,
        "package_metadata": package_metadata,
        "transport": transport,
        "target_exists": target_codex_home.exists(),
        "packaged_projects": package_metadata.get("projects", []),
        "project_restore_destination": str(project_destination) if project_destination else None,
        "mappings": [{"old": item.old, "new": item.new} for item in mappings],
        "source_inventory": source_inventory,
        "desktop_state_safety": {
            "available": bool(desktop_payload),
            "payload": str(desktop_payload) if desktop_payload else None,
            "restore": "manual-only",
        },
        "target_inventory": inspect_codex_home(target_codex_home),
        "requires": [
            "Codex/ChatGPT and Codex CLI fully stopped",
            "reviewed path mappings",
            "--replace-existing and --apply for a non-empty destination",
        ],
    }


def apply_restore(
    package: Path,
    target_codex_home: Path,
    mappings: list[PathMapping],
    *,
    replace_existing: bool,
    project_destination: Path | None = None,
    allow_unresolved_paths: bool = False,
) -> dict[str, Any]:
    require_apps_stopped()
    plan = build_restore_plan(package, target_codex_home, mappings, project_destination)
    if not plan["manifest"]["ok"]:
        raise MigrationError("Refusing to restore a package whose manifest does not verify")
    if target_codex_home.exists() and any(target_codex_home.iterdir()) and not replace_existing:
        raise MigrationError("Target Codex home is non-empty; review the plan then add --replace-existing --apply")

    timestamp = utc_timestamp()
    parent = target_codex_home.parent
    parent.mkdir(parents=True, exist_ok=True)
    stage = parent / f"{target_codex_home.name}.codex-migration-stage-{timestamp}"
    backup = parent / f"{target_codex_home.name}.before-codex-migration-{timestamp}"
    retired = parent / f"{target_codex_home.name}.replaced-by-codex-migration-{timestamp}"
    if stage.exists() or backup.exists() or retired.exists():
        raise MigrationError("Timestamp collision while creating restore paths; retry")

    project_stage: Path | None = None
    project_targets: list[tuple[Path, Path]] = []
    packaged_projects = [item for item in plan["packaged_projects"] if isinstance(item, str)]
    if project_destination and packaged_projects:
        project_destination = project_destination.expanduser()
        project_stage = project_destination.parent / f".{project_destination.name}.codex-migration-stage-{timestamp}"
        if project_stage.exists():
            raise MigrationError("Timestamp collision while staging projects; retry")
        for name in packaged_projects:
            source = _payload_path(package, plan["package_metadata"], "project", name)
            target = project_destination / name
            if not source.exists():
                raise MigrationError(f"Package metadata names a missing project payload: {name}")
            if target.exists():
                raise MigrationError(f"Refusing to overwrite existing project folder: {target}")
            if plan["transport"] == "archive":
                _safe_extract_tar(source, project_stage / name, f"projects/{name}")
            else:
                copy_tree(source, project_stage / name)
            project_targets.append((project_stage / name, target))

    moved_projects: list[tuple[Path, Path]] = []
    try:
        if target_codex_home.exists():
            copy_tree(target_codex_home, backup)
            copy_tree(target_codex_home, stage)
        else:
            stage.mkdir(parents=True)
        codex_payload = _payload_path(package, plan["package_metadata"], "codex")
        if plan["transport"] == "archive":
            _safe_extract_tar(codex_payload, stage, "codex-home")
        else:
            copy_tree(codex_payload, stage)
        rewrite_counts = rewrite_staged_paths(stage, mappings)
        for staged_project, project_target in project_targets:
            project_target.parent.mkdir(parents=True, exist_ok=True)
            staged_project.rename(project_target)
            moved_projects.append((staged_project, project_target))
        stage_inventory = inspect_codex_home(stage)
        failing_databases = [db for db in stage_inventory["sqlite"] if db.get("quick_check") not in (None, "ok")]
        if failing_databases:
            raise MigrationError(f"Staged SQLite validation failed: {failing_databases}")
        unresolved_paths = stage_inventory["stale_project_roots"] + stage_inventory["stale_workspace_references"]
        if unresolved_paths and not allow_unresolved_paths:
            raise MigrationError(
                "Staged Codex state still refers to missing project/workspace paths. "
                "Correct --map or --restore-projects-to; use --allow-unresolved-paths only after reviewing the report."
            )

        if target_codex_home.exists():
            target_codex_home.rename(retired)
        stage.rename(target_codex_home)
        if project_stage and project_stage.exists():
            project_stage.rmdir()
    except Exception:
        for staged_project, project_target in reversed(moved_projects):
            if project_target.exists() and not staged_project.exists():
                staged_project.parent.mkdir(parents=True, exist_ok=True)
                project_target.rename(staged_project)
        if stage.exists():
            shutil.rmtree(stage, ignore_errors=True)
        if not target_codex_home.exists() and retired.exists():
            retired.rename(target_codex_home)
        raise

    report = {
        "status": "completed-with-warnings" if unresolved_paths else "completed",
        "plan": plan,
        "backup": str(backup) if backup.exists() else None,
        "retired_target": str(retired) if retired.exists() else None,
        "rewrite_counts": rewrite_counts,
        "restored_projects": [str(target) for _, target in project_targets],
        "target_inventory": inspect_codex_home(target_codex_home),
        "unresolved_paths": unresolved_paths,
        "unapplied_desktop_state_safety": plan["desktop_state_safety"],
        "next_steps": [
            "Open Codex and sign in again.",
            "Open each restored project folder through Codex Desktop.",
            "Create a new task in each project and keep the source/package until verified.",
        ],
    }
    write_json(target_codex_home / "codex-migration-restore-report.json", report)
    return report

from __future__ import annotations

import json
import os
import shutil
import sqlite3
from pathlib import Path
from typing import Any

from .errors import MigrationError
from .inventory import inspect_codex_home
from .manifest import verify_manifest
from .mapping import PathMapping
from .rewrite import rewrite_structured_paths
from .util import copy_tree, require_apps_stopped, utc_timestamp, write_json


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
            if "cwd" in columns:
                rows = list(connection.execute("SELECT rowid, cwd FROM threads WHERE cwd IS NOT NULL"))
                for rowid, cwd in rows:
                    rewritten, count = rewrite_structured_paths(cwd, mappings, key="cwd")
                    if count:
                        connection.execute("UPDATE threads SET cwd = ? WHERE rowid = ?", (rewritten, rowid))
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
    package_metadata = json.loads((package / "package.json").read_text(encoding="utf-8"))
    source_profile = package / "codex-home"
    if not source_profile.is_dir():
        raise MigrationError("Package does not contain codex-home/")
    return {
        "schema": 1,
        "package": str(package),
        "target_codex_home": str(target_codex_home),
        "manifest": verification,
        "package_metadata": package_metadata,
        "target_exists": target_codex_home.exists(),
        "packaged_projects": package_metadata.get("projects", []),
        "project_restore_destination": str(project_destination) if project_destination else None,
        "mappings": [{"old": item.old, "new": item.new} for item in mappings],
        "source_inventory": inspect_codex_home(source_profile),
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
            source = package / "projects" / name
            target = project_destination / name
            if not source.is_dir():
                raise MigrationError(f"Package metadata names a missing project: {name}")
            if target.exists():
                raise MigrationError(f"Refusing to overwrite existing project folder: {target}")
            copy_tree(source, project_stage / name)
            project_targets.append((project_stage / name, target))

    try:
        if target_codex_home.exists():
            copy_tree(target_codex_home, backup)
            copy_tree(target_codex_home, stage)
        else:
            stage.mkdir(parents=True)
        copy_tree(package / "codex-home", stage)
        rewrite_counts = rewrite_staged_paths(stage, mappings)
        stage_inventory = inspect_codex_home(stage)
        failing_databases = [db for db in stage_inventory["sqlite"] if db.get("quick_check") not in (None, "ok")]
        if failing_databases:
            raise MigrationError(f"Staged SQLite validation failed: {failing_databases}")

        if target_codex_home.exists():
            target_codex_home.rename(retired)
        stage.rename(target_codex_home)
        for staged_project, project_target in project_targets:
            project_target.parent.mkdir(parents=True, exist_ok=True)
            staged_project.rename(project_target)
        if project_stage and project_stage.exists():
            project_stage.rmdir()
    except Exception:
        if stage.exists():
            shutil.rmtree(stage, ignore_errors=True)
        if not target_codex_home.exists() and retired.exists():
            retired.rename(target_codex_home)
        raise

    report = {
        "status": "completed",
        "plan": plan,
        "backup": str(backup) if backup.exists() else None,
        "retired_target": str(retired) if retired.exists() else None,
        "rewrite_counts": rewrite_counts,
        "restored_projects": [str(target) for _, target in project_targets],
        "target_inventory": inspect_codex_home(target_codex_home),
        "next_steps": [
            "Open Codex and sign in again.",
            "Open each restored project folder through Codex Desktop.",
            "Create a new task in each project and keep the source/package until verified.",
        ],
    }
    write_json(target_codex_home / "codex-migration-restore-report.json", report)
    return report

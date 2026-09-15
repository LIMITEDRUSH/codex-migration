from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .util import host_metadata, iter_files


def _sqlite_summary(path: Path) -> dict[str, Any]:
    summary: dict[str, Any] = {"file": path.name, "quick_check": None, "threads": None, "error": None}
    try:
        connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        try:
            summary["quick_check"] = connection.execute("PRAGMA quick_check").fetchone()[0]
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "threads" in tables:
                summary["threads"] = connection.execute("SELECT COUNT(*) FROM threads").fetchone()[0]
        finally:
            connection.close()
    except (OSError, sqlite3.Error) as error:
        summary["error"] = str(error)
    return summary


def inspect_codex_home(codex_home: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema": 1,
        "codex_home": str(codex_home),
        "host": host_metadata(),
        "exists": codex_home.is_dir(),
        "file_count": 0,
        "session_files": 0,
        "archived_session_files": 0,
        "sqlite": [],
        "global_state": {},
        "stale_project_roots": [],
    }
    if not codex_home.is_dir():
        return result
    for file_path in iter_files(codex_home):
        result["file_count"] += 1
        relative = file_path.relative_to(codex_home)
        if relative.parts and relative.parts[0] == "sessions" and file_path.suffix == ".jsonl":
            result["session_files"] += 1
        if relative.parts and relative.parts[0] == "archived_sessions" and file_path.suffix == ".jsonl":
            result["archived_session_files"] += 1
        if file_path.suffix == ".sqlite":
            summary = _sqlite_summary(file_path)
            summary["file"] = relative.as_posix()
            result["sqlite"].append(summary)
    global_state = codex_home / ".codex-global-state.json"
    if global_state.is_file():
        try:
            state = json.loads(global_state.read_text(encoding="utf-8"))
            for field in ("local-projects", "thread-project-assignments", "projectless-thread-ids", "project-order"):
                value = state.get(field)
                result["global_state"][field] = len(value) if isinstance(value, (dict, list)) else None
            projects = state.get("local-projects")
            if isinstance(projects, dict):
                for project_id, project in projects.items():
                    if not isinstance(project, dict):
                        continue
                    for root in project.get("rootPaths", []):
                        if isinstance(root, str) and not Path(root).is_dir():
                            result["stale_project_roots"].append({"project_id": project_id, "path": root})
        except (OSError, json.JSONDecodeError) as error:
            result["global_state"]["error"] = str(error)
    return result

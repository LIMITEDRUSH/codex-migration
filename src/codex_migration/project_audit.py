from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from .errors import MigrationError


def _git(project: Path, *arguments: str) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            ["git", "-C", str(project), *arguments], capture_output=True, text=True, check=False
        )
    except OSError as error:
        return {"available": False, "error": str(error)}
    return {
        "available": True,
        "returncode": completed.returncode,
        "stdout": completed.stdout.rstrip("\r\n"),
        "stderr": completed.stderr.rstrip("\r\n"),
    }


def audit_project(project: Path) -> dict[str, Any]:
    """Read-only project and Git health evidence for post-migration acceptance."""
    project = project.expanduser().resolve()
    if not project.is_dir():
        raise MigrationError(f"Project directory does not exist: {project}")
    root = _git(project, "rev-parse", "--show-toplevel")
    report: dict[str, Any] = {"project": str(project), "git": {"repository": root}}
    if not root.get("available") or root.get("returncode") != 0:
        return report
    report["git"].update(
        {
            "head": _git(project, "rev-parse", "--verify", "HEAD"),
            "status": _git(project, "status", "--porcelain=v1", "--branch"),
            "worktrees": _git(project, "worktree", "list", "--porcelain"),
        }
    )
    return report

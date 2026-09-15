"""Explain exactly what an export will and will not cover.

This deliberately identifies project *roots*, rather than trying to guess individual
files from conversation text.  A project root is the smallest dependable unit for a
working restore: it preserves uncommitted work, generated configuration, attachments,
and data that source-control alone may not contain.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .package import discover_registered_projects, merge_projects


def build_scope(codex_home: Path, additional_projects: list[tuple[str, Path]]) -> dict[str, Any]:
    """Return the selected migration roots without reading project file contents."""
    codex_home = codex_home.expanduser()
    registered = discover_registered_projects(codex_home)
    selected = merge_projects(registered, additional_projects)
    registered_paths = {path.resolve() for _, path in registered}
    return {
        "schema": 1,
        "codex_home": str(codex_home),
        "portable_codex_profile": {
            "path": str(codex_home),
            "included": "sessions, archived sessions, supported state, skills, plugins, and portable attachments",
            "excluded": "authentication, browser credentials, locks, SQLite WAL/SHM, caches, and runtime paths",
        },
        "projects": [
            {
                "name": name,
                "path": str(path),
                "selection": "registered-by-codex" if path.resolve() in registered_paths else "explicitly-supplied",
                "copy_rule": "entire project root, byte-for-byte; no source-file guessing or implicit exclusions",
            }
            for name, path in selected
        ],
        "coverage_boundary": {
            "included": "the portable Codex profile and every project root listed above",
            "requires_explicit_addition": "any required folder that has never been registered as a Codex project",
            "not_scanned": "arbitrary folders elsewhere on the computer, even if a conversation happened to mention them",
        },
    }

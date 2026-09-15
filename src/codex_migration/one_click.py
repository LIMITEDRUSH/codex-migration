from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .errors import MigrationError
from .mapping import PathMapping
from .restore import apply_restore
from .util import utc_timestamp, write_json


def _metadata(package: Path) -> dict[str, Any]:
    try:
        metadata = json.loads((package / "package.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MigrationError(f"Cannot read package metadata: {error}") from error
    if not isinstance(metadata, dict):
        raise MigrationError("Package metadata must be a JSON object")
    return metadata


def _unique_project_destination(base: Path, project_names: list[str]) -> Path:
    if not base.exists() or not any((base / name).exists() for name in project_names):
        return base
    return base.with_name(f"{base.name}-{utc_timestamp()}")


def restore_everything(
    package: Path,
    *,
    target_codex_home: Path | None = None,
    project_destination: Path | None = None,
) -> dict[str, Any]:
    """Apply a package's recorded project mapping without asking the user to type paths."""
    package = package.expanduser().resolve()
    metadata = _metadata(package)
    source_codex_home = metadata.get("source_codex_home")
    project_sources = metadata.get("project_sources")
    packaged_projects = metadata.get("projects")
    if not isinstance(source_codex_home, str) or not source_codex_home:
        raise MigrationError("This package predates one-click restore; use the reviewed restore command instead")
    if not isinstance(project_sources, dict) or not isinstance(packaged_projects, list):
        raise MigrationError("Package is missing recorded source project paths for one-click restore")
    project_names = [name for name in packaged_projects if isinstance(name, str)]
    if len(project_names) != len(packaged_projects) or len(set(project_names)) != len(project_names):
        raise MigrationError("Package project metadata is malformed")

    target_codex_home = (target_codex_home or (Path.home() / ".codex")).expanduser()
    # Keep default restored projects outside Documents: on Windows that folder is often silently redirected to OneDrive.
    default_projects = Path.home() / "Codex-Restored-Projects"
    project_destination = (project_destination or default_projects).expanduser()
    project_destination = _unique_project_destination(project_destination, project_names)

    mappings = [PathMapping(old=source_codex_home.rstrip("\\/"), new=str(target_codex_home))]
    for name in project_names:
        old_path = project_sources.get(name)
        if not isinstance(old_path, str) or not old_path:
            raise MigrationError(f"Package has no source path recorded for project {name!r}")
        mappings.append(PathMapping(old=old_path.rstrip("\\/"), new=str(project_destination / name)))

    result = apply_restore(
        package,
        target_codex_home,
        mappings,
        replace_existing=True,
        project_destination=project_destination if project_names else None,
        allow_unresolved_paths=False,
    )
    result["one_click"] = {
        "generated_mappings": [{"old": mapping.old, "new": mapping.new} for mapping in mappings],
        "project_destination": str(project_destination) if project_names else None,
        "credential_note": "Sign in to Codex again on this computer; credentials were intentionally not restored.",
    }
    write_json(target_codex_home / "codex-migration-restore-report.json", result)
    return result

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .errors import MigrationError
from .inventory import inspect_codex_home
from .manifest import verify_manifest
from .mapping import parse_mapping
from .package import (
    default_desktop_state_source,
    discover_registered_projects,
    export_package,
    merge_projects,
    parse_project,
)
from .project_audit import audit_project
from .one_click import restore_everything
from .restore import apply_restore, build_restore_plan
from .util import write_json


def _print(payload: object) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))


def _path(value: str) -> Path:
    return Path(value).expanduser()


def parser() -> argparse.ArgumentParser:
    command_parser = argparse.ArgumentParser(prog="codex-migration", description="Safe Codex Desktop migration toolkit")
    subcommands = command_parser.add_subparsers(dest="command", required=True)

    inspect = subcommands.add_parser("inspect", help="Inspect a Codex home without changing it")
    inspect.add_argument("--codex-home", type=_path, required=True)
    inspect.add_argument("--report", type=_path, help="Optional JSON output path")

    export = subcommands.add_parser("export", help="Create a verified portable package")
    export.add_argument("--codex-home", type=_path, required=True)
    export.add_argument("--output", type=_path, required=True)
    export.add_argument("--project", action="append", default=[], metavar="NAME=PATH", help="Explicitly include a project directory")
    export.add_argument(
        "--no-registered-projects",
        action="store_true",
        help="Do not automatically include every existing project registered in Codex",
    )
    desktop_state = export.add_mutually_exclusive_group()
    desktop_state.add_argument("--desktop-state", type=_path, help="Additional Codex desktop-state directory to retain as a safety snapshot")
    desktop_state.add_argument("--no-desktop-state", action="store_true", help="Do not include the conventional desktop-state safety snapshot")
    export.add_argument(
        "--transport",
        choices=("archive", "directory"),
        default="archive",
        help="Package format; archive is the USB-safe default, directory is for local filesystems only",
    )

    verify = subcommands.add_parser("verify", help="Verify every file in a package")
    verify.add_argument("--package", type=_path, required=True)

    project_audit = subcommands.add_parser("project-audit", help="Read-only Git and project audit after restoration")
    project_audit.add_argument("--project", type=_path, required=True)

    restore = subcommands.add_parser("restore", help="Plan or apply a staged restore")
    restore.add_argument("--package", type=_path, required=True)
    restore.add_argument("--target-codex-home", type=_path, required=True)
    restore.add_argument("--map", action="append", default=[], metavar="OLD=NEW")
    restore.add_argument("--restore-projects-to", type=_path, help="Copy packaged projects as children of this directory")
    restore.add_argument("--report", type=_path, help="Write plan/report JSON to this path")
    restore.add_argument("--replace-existing", action="store_true", help="Allow replacing a non-empty target after backup")
    restore.add_argument("--apply", action="store_true", help="Actually write the staged restore")
    restore.add_argument(
        "--allow-unresolved-paths",
        action="store_true",
        help="Apply despite stale project/workspace paths after review; normally this is refused",
    )

    one_click_restore = subcommands.add_parser(
        "one-click-restore", help="Restore a current self-contained USB package with recorded automatic mappings"
    )
    one_click_restore.add_argument("--package", type=_path, required=True)
    one_click_restore.add_argument("--target-codex-home", type=_path)
    one_click_restore.add_argument("--restore-projects-to", type=_path)
    return command_parser


def main(argv: list[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        if arguments.command == "inspect":
            result = inspect_codex_home(arguments.codex_home)
            if arguments.report:
                write_json(arguments.report, result)
            _print(result)
            return 0
        if arguments.command == "verify":
            result = verify_manifest(arguments.package)
            _print(result)
            return 0 if result["ok"] else 2
        if arguments.command == "project-audit":
            _print(audit_project(arguments.project))
            return 0
        if arguments.command == "one-click-restore":
            _print(
                restore_everything(
                    arguments.package,
                    target_codex_home=arguments.target_codex_home,
                    project_destination=arguments.restore_projects_to,
                )
            )
            return 0
        if arguments.command == "export":
            additional_projects = [parse_project(value) for value in arguments.project]
            registered_projects = [] if arguments.no_registered_projects else discover_registered_projects(arguments.codex_home)
            projects = merge_projects(registered_projects, additional_projects)
            desktop_state = None
            if not arguments.no_desktop_state:
                desktop_state = arguments.desktop_state or default_desktop_state_source(arguments.codex_home)
            result = export_package(
                arguments.codex_home, arguments.output, projects, transport=arguments.transport, desktop_state=desktop_state
            )
            result["registered_projects"] = [name for name, _ in registered_projects]
            result["additional_projects"] = [name for name, _ in additional_projects]
            _print(result)
            return 0
        if arguments.command == "restore":
            mappings = [parse_mapping(value) for value in arguments.map]
            if arguments.apply:
                if not arguments.replace_existing:
                    raise MigrationError("--apply requires --replace-existing to make replacement explicit")
                result = apply_restore(
                    arguments.package,
                    arguments.target_codex_home,
                    mappings,
                    replace_existing=True,
                    project_destination=arguments.restore_projects_to,
                    allow_unresolved_paths=arguments.allow_unresolved_paths,
                )
            else:
                result = build_restore_plan(
                    arguments.package, arguments.target_codex_home, mappings, arguments.restore_projects_to
                )
                result["status"] = "planned"
            if arguments.report:
                write_json(arguments.report, result)
            _print(result)
            return 0
    except MigrationError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

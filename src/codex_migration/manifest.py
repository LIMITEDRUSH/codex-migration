from __future__ import annotations

from pathlib import Path

from .errors import MigrationError
from .util import iter_files, relative_posix, sha256_file


MANIFEST_NAME = "MANIFEST.sha256"


def write_manifest(package_root: Path) -> int:
    lines = []
    for file_path in iter_files(package_root):
        if file_path.name == MANIFEST_NAME:
            continue
        lines.append(f"{sha256_file(file_path)}  {relative_posix(file_path, package_root)}")
    (package_root / MANIFEST_NAME).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(lines)


def verify_manifest(package_root: Path) -> dict[str, object]:
    manifest = package_root / MANIFEST_NAME
    if not manifest.is_file():
        raise MigrationError(f"Package manifest is missing: {manifest}")
    checked = 0
    failures: list[str] = []
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            expected, relative = line.split("  ", 1)
        except ValueError:
            failures.append(f"Malformed manifest line: {line!r}")
            continue
        target = package_root / Path(relative)
        checked += 1
        if not target.is_file():
            failures.append(f"Missing: {relative}")
        elif sha256_file(target) != expected:
            failures.append(f"Hash mismatch: {relative}")
    return {"checked": checked, "ok": not failures, "failures": failures}

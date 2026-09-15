from __future__ import annotations

import re
from dataclasses import dataclass

from .errors import MigrationError


WINDOWS_PATH = re.compile(r"^[A-Za-z]:[\\/]")


@dataclass(frozen=True)
class PathMapping:
    old: str
    new: str

    @property
    def old_key(self) -> str:
        return normalize_for_match(self.old)


def normalize_for_match(value: str) -> str:
    normalized = value.replace("\\", "/").rstrip("/")
    if WINDOWS_PATH.match(value):
        return normalized.casefold()
    return normalized


def parse_mapping(value: str) -> PathMapping:
    if "=" not in value:
        raise MigrationError(f"Mapping must be OLD=NEW, received: {value!r}")
    old, new = (part.strip() for part in value.split("=", 1))
    if not old or not new:
        raise MigrationError(f"Mapping must include both OLD and NEW, received: {value!r}")
    return PathMapping(old=old.rstrip("\\/"), new=new.rstrip("\\/"))


def map_path(value: str, mappings: list[PathMapping]) -> str:
    """Map the longest matching normalized prefix, otherwise return value unchanged."""
    raw_normalized = value.replace("\\", "/").rstrip("/")
    key = normalize_for_match(value)
    matches = [mapping for mapping in mappings if key == mapping.old_key or key.startswith(mapping.old_key + "/")]
    if not matches:
        return value
    mapping = max(matches, key=lambda item: len(item.old_key))
    # Matching a Windows path is case-insensitive, but the restored path may be
    # displayed on a case-sensitive target. Preserve suffix spelling exactly.
    suffix = raw_normalized[len(mapping.old.rstrip("\\/").replace("\\", "/")) :].lstrip("/")
    if not suffix:
        return mapping.new
    separator = "\\" if WINDOWS_PATH.match(mapping.new) else "/"
    return mapping.new + separator + suffix.replace("/", separator)

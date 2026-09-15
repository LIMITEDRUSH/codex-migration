from __future__ import annotations

from copy import deepcopy
from typing import Any

from .mapping import PathMapping, map_path


SCALAR_PATH_KEYS = {
    "cwd",
    "path",
    "rootPath",
    "workspaceRoot",
    "workspace_root",
    "workspacePath",
    "rollout_path",
    "rolloutPath",
}
LIST_PATH_KEYS = {
    "rootPaths",
    "workspace_roots",
    "workspaceRoots",
    "writable_roots",
    "writableRoots",
    "electron-saved-workspace-roots",
    "active-workspace-roots",
}
DICT_SCALAR_PATH_VALUES = {
    "thread-workspace-root-hints",
    "thread-projectless-output-directories",
}
DICT_LIST_PATH_VALUES = {"thread-writable-roots"}
SKIP_SUBTREES = {"prompt-history", "prompt_history", "messages", "items", "content"}


def rewrite_structured_paths(value: Any, mappings: list[PathMapping], *, key: str | None = None) -> tuple[Any, int]:
    """Copy a JSON value and rewrite only known path-bearing structural fields."""
    if key in SKIP_SUBTREES:
        return deepcopy(value), 0
    if key in SCALAR_PATH_KEYS and isinstance(value, str):
        rewritten = map_path(value, mappings)
        return rewritten, int(rewritten != value)
    if key in LIST_PATH_KEYS and isinstance(value, list):
        changed = 0
        rewritten_items = []
        for item in value:
            if isinstance(item, str):
                replacement = map_path(item, mappings)
                changed += int(replacement != item)
                rewritten_items.append(replacement)
            else:
                rewritten_items.append(deepcopy(item))
        return rewritten_items, changed
    if key == "workspace_by_cwd" and isinstance(value, dict):
        rewritten_dict: dict[str, Any] = {}
        changed = 0
        for old_key, item in value.items():
            new_key = map_path(old_key, mappings)
            changed += int(new_key != old_key)
            rewritten_item, item_changes = rewrite_structured_paths(item, mappings)
            changed += item_changes
            rewritten_dict[new_key] = rewritten_item
        return rewritten_dict, changed
    if key in DICT_SCALAR_PATH_VALUES and isinstance(value, dict):
        rewritten_dict = {}
        changed = 0
        for child_key, item in value.items():
            if isinstance(item, str):
                replacement = map_path(item, mappings)
                changed += int(replacement != item)
                rewritten_dict[child_key] = replacement
            else:
                rewritten_dict[child_key] = deepcopy(item)
        return rewritten_dict, changed
    if key in DICT_LIST_PATH_VALUES and isinstance(value, dict):
        rewritten_dict = {}
        changed = 0
        for child_key, item in value.items():
            if isinstance(item, list):
                replacements = []
                for path in item:
                    if isinstance(path, str):
                        replacement = map_path(path, mappings)
                        changed += int(replacement != path)
                        replacements.append(replacement)
                    else:
                        replacements.append(deepcopy(path))
                rewritten_dict[child_key] = replacements
            else:
                rewritten_dict[child_key] = deepcopy(item)
        return rewritten_dict, changed
    if isinstance(value, dict):
        changed = 0
        rewritten = {}
        for child_key, item in value.items():
            child, item_changes = rewrite_structured_paths(item, mappings, key=child_key)
            rewritten[child_key] = child
            changed += item_changes
        return rewritten, changed
    if isinstance(value, list):
        changed = 0
        rewritten_list = []
        for item in value:
            child, item_changes = rewrite_structured_paths(item, mappings)
            rewritten_list.append(child)
            changed += item_changes
        return rewritten_list, changed
    return deepcopy(value), 0

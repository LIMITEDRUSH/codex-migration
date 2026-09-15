from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from codex_migration.scope import build_scope


class ScopeTests(unittest.TestCase):
    def test_scope_distinguishes_registered_and_explicit_roots(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            codex_home = root / ".codex"
            registered = root / "Registered"
            explicit = root / "Explicit"
            codex_home.mkdir()
            registered.mkdir()
            explicit.mkdir()
            (codex_home / ".codex-global-state.json").write_text(
                json.dumps({"local-projects": {"one": {"rootPaths": [str(registered)]}}}), encoding="utf-8"
            )

            scope = build_scope(codex_home, [("Extra", explicit)])

            self.assertEqual(
                scope["projects"],
                [
                    {
                        "name": "Extra",
                        "path": str(explicit),
                        "selection": "explicitly-supplied",
                        "copy_rule": "entire project root, byte-for-byte; no source-file guessing or implicit exclusions",
                    },
                    {
                        "name": "Registered",
                        "path": str(registered),
                        "selection": "registered-by-codex",
                        "copy_rule": "entire project root, byte-for-byte; no source-file guessing or implicit exclusions",
                    },
                ],
            )


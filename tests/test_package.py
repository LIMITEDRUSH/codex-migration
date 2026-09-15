import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from codex_migration.manifest import verify_manifest
from codex_migration.package import export_package


class PackageTests(unittest.TestCase):
    def test_export_excludes_auth_and_verifies_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            codex_home = root / ".codex"
            (codex_home / "sessions" / "2026").mkdir(parents=True)
            (codex_home / "sessions" / "2026" / "rollout.jsonl").write_text('{"cwd":"C:/old"}\n', encoding="utf-8")
            (codex_home / "auth.json").write_text('{"secret":true}', encoding="utf-8")
            (codex_home / ".codex-global-state.json").write_text(json.dumps({"local-projects": {}}), encoding="utf-8")
            output = root / "package"
            with patch("codex_migration.package.require_apps_stopped"):
                result = export_package(codex_home, output, [])
            self.assertGreater(result["manifest_entries"], 0)
            self.assertFalse((output / "codex-home" / "auth.json").exists())
            self.assertTrue(verify_manifest(output)["ok"])

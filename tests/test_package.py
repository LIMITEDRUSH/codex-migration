import json
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from codex_migration.manifest import verify_manifest
from codex_migration.errors import MigrationError
from codex_migration.package import discover_registered_projects, export_package, merge_projects


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
            self.assertEqual(result["transport"], "archive")
            self.assertFalse((output / "codex-home").exists())
            with tarfile.open(output / "archives" / "codex-home.tar") as archive:
                names = archive.getnames()
            self.assertIn("codex-home/sessions/2026/rollout.jsonl", names)
            self.assertNotIn("codex-home/auth.json", names)
            self.assertEqual(result["source_inventory"]["portable_file_count"], 2)
            self.assertEqual(result["source_inventory"]["volatile_file_count"], 1)
            coverage = json.loads((output / "reports" / "coverage.json").read_text(encoding="utf-8"))
            self.assertEqual(coverage["included"]["portable_codex_profile"]["summary"]["files"], 2)
            self.assertIn("not_automatically_discovered", coverage)
            self.assertTrue(verify_manifest(output)["ok"])

    def test_discovers_registered_projects_and_refuses_missing_roots(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            codex_home = root / ".codex"
            project = root / "StudyAssistant"
            codex_home.mkdir()
            project.mkdir()
            (codex_home / ".codex-global-state.json").write_text(
                json.dumps({"local-projects": {"p": {"rootPaths": [str(project)]}}}), encoding="utf-8"
            )
            self.assertEqual(discover_registered_projects(codex_home), [("StudyAssistant", project)])
            self.assertEqual(merge_projects([("StudyAssistant", project)], [("PreferredName", project)]), [("PreferredName", project)])
            (codex_home / ".codex-global-state.json").write_text(
                json.dumps({"local-projects": {"p": {"rootPaths": [str(root / "missing")]}}}), encoding="utf-8"
            )
            with self.assertRaises(MigrationError):
                discover_registered_projects(codex_home)

    def test_desktop_state_is_packaged_as_manual_only_safety_snapshot(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            codex_home = root / ".codex"
            desktop_state = root / "desktop-state"
            codex_home.mkdir()
            desktop_state.mkdir()
            (codex_home / ".codex-global-state.json").write_text('{"local-projects":{}}', encoding="utf-8")
            (desktop_state / "ui-state.json").write_text('{"saved":true}', encoding="utf-8")
            output = root / "package"
            with patch("codex_migration.package.require_apps_stopped"):
                result = export_package(codex_home, output, [], desktop_state=desktop_state)
            self.assertEqual(result["desktop_state_safety"]["files"], 1)
            with tarfile.open(output / "archives" / "desktop-state-safety.tar") as archive:
                self.assertIn("desktop-state-safety/ui-state.json", archive.getnames())

    def test_manifest_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as temp:
            package = Path(temp) / "package"
            package.mkdir()
            (package / "MANIFEST.sha256").write_text("not-a-hash  ../outside\n", encoding="utf-8")
            result = verify_manifest(package)
            self.assertFalse(result["ok"])
            self.assertIn("Unsafe manifest path: ../outside", result["failures"])

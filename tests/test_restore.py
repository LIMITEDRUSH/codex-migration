import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from codex_migration.errors import MigrationError
from codex_migration.manifest import write_manifest
from codex_migration.mapping import parse_mapping
from codex_migration.package import export_package
from codex_migration.restore import apply_restore, rewrite_staged_paths


class RestoreTests(unittest.TestCase):
    def test_rewrites_sqlite_cwd_and_validates(self):
        with tempfile.TemporaryDirectory() as temp:
            stage = Path(temp)
            database = stage / "state_5.sqlite"
            connection = sqlite3.connect(database)
            connection.execute("CREATE TABLE threads (cwd TEXT, rollout_path TEXT, sandbox_policy TEXT)")
            connection.execute(
                "INSERT INTO threads VALUES (?, ?, ?)",
                (
                    r"C:\Users\Lenovo\Desktop\YEAR4",
                    r"C:\Users\Lenovo\Desktop\YEAR4\sessions\rollout.jsonl",
                    '{"workspace_roots":["C:\\\\Users\\\\Lenovo\\\\Desktop\\\\YEAR4"]}',
                ),
            )
            connection.execute("CREATE TABLE project_roots (path TEXT)")
            connection.execute("INSERT INTO project_roots VALUES (?)", (r"C:\Users\Lenovo\Desktop\YEAR4",))
            connection.commit()
            connection.close()
            counts = rewrite_staged_paths(stage, [parse_mapping(r"C:\Users\Lenovo\Desktop\YEAR4=/Users/me/StudyAssistant")])
            self.assertEqual(counts["sqlite"], 4)
            connection = sqlite3.connect(database)
            cwd = connection.execute("SELECT cwd FROM threads").fetchone()[0]
            self.assertEqual(cwd, "/Users/me/StudyAssistant")
            rollout_path = connection.execute("SELECT rollout_path FROM threads").fetchone()[0]
            self.assertEqual(rollout_path, "/Users/me/StudyAssistant/sessions/rollout.jsonl")
            root = connection.execute("SELECT path FROM project_roots").fetchone()[0]
            self.assertEqual(root, "/Users/me/StudyAssistant")
            self.assertEqual(connection.execute("PRAGMA quick_check").fetchone()[0], "ok")
            connection.close()

    def test_apply_restore_backs_up_target_and_maps_global_state(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / "package"
            source_home = package / "codex-home"
            source_home.mkdir(parents=True)
            (package / "package.json").write_text('{"projects": []}', encoding="utf-8")
            (package / "reports").mkdir()
            (package / "reports" / "source-inventory.json").write_text("{}", encoding="utf-8")
            (source_home / ".codex-global-state.json").write_text(
                '{"local-projects":{"p":{"rootPaths":["C:\\\\Old\\\\Project"]}},'
                '"thread-workspace-root-hints":{"t":"C:\\\\Old\\\\Project"}}',
                encoding="utf-8",
            )
            database = source_home / "state_5.sqlite"
            connection = sqlite3.connect(database)
            connection.execute("CREATE TABLE threads (cwd TEXT)")
            connection.execute("INSERT INTO threads VALUES (?)", (r"C:\Old\Project",))
            connection.commit()
            connection.close()
            write_manifest(package)

            target = root / ".codex"
            target.mkdir()
            (target / "keep.txt").write_text("old", encoding="utf-8")
            with patch("codex_migration.restore.require_apps_stopped"):
                result = apply_restore(
                    package,
                    target,
                    [parse_mapping(r"C:\Old\Project=/Users/me/Project")],
                    replace_existing=True,
                    allow_unresolved_paths=True,
                )
            self.assertEqual(result["status"], "completed-with-warnings")
            self.assertEqual((target / "keep.txt").read_text(encoding="utf-8"), "old")
            restored = (target / ".codex-global-state.json").read_text(encoding="utf-8")
            self.assertIn("/Users/me/Project", restored)
            self.assertTrue(result["backup"])
            self.assertTrue(Path(result["backup"]).is_dir())

    def test_archive_package_restores_without_cloud_or_directory_payload(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source_home = root / "source-codex"
            (source_home / "sessions" / "2026").mkdir(parents=True)
            (source_home / "sessions" / "2026" / "rollout.jsonl").write_text('{"type":"session"}\n', encoding="utf-8")
            (source_home / ".codex-global-state.json").write_text('{"local-projects":{}}', encoding="utf-8")
            package = root / "usb-package"
            with patch("codex_migration.package.require_apps_stopped"):
                export_package(source_home, package, [])
            self.assertTrue((package / "archives" / "codex-home.tar").is_file())
            self.assertFalse((package / "codex-home").exists())

            target = root / "target-codex"
            target.mkdir()
            (target / "target-only.txt").write_text("keep", encoding="utf-8")
            with patch("codex_migration.restore.require_apps_stopped"):
                result = apply_restore(package, target, [], replace_existing=True)
            self.assertEqual(result["status"], "completed")
            self.assertTrue((target / "target-only.txt").is_file())
            self.assertTrue((target / "sessions" / "2026" / "rollout.jsonl").is_file())

    def test_refuses_unresolved_workspace_paths_without_explicit_override(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / "package"
            source_home = package / "codex-home"
            source_home.mkdir(parents=True)
            (package / "reports").mkdir()
            (package / "reports" / "source-inventory.json").write_text("{}", encoding="utf-8")
            (package / "package.json").write_text('{"projects": []}', encoding="utf-8")
            (source_home / ".codex-global-state.json").write_text(
                '{"local-projects":{"p":{"rootPaths":["C:\\\\Old\\\\Missing"]}}}', encoding="utf-8"
            )
            write_manifest(package)
            target = root / "target-codex"
            with patch("codex_migration.restore.require_apps_stopped"):
                with self.assertRaises(MigrationError):
                    apply_restore(
                        package,
                        target,
                        [parse_mapping(r"C:\Old\Missing=/does/not/exist")],
                        replace_existing=True,
                    )
            self.assertFalse(target.exists())

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from codex_migration.one_click import restore_everything
from codex_migration.package import export_package


class OneClickWorkflowTests(unittest.TestCase):
    def test_self_contained_package_restores_project_with_automatic_mapping(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source_home = root / "source-codex"
            source_project = root / "StudyAssistant"
            source_home.mkdir()
            source_project.mkdir()
            (source_project / "main.py").write_text("print('study')\n", encoding="utf-8")
            (source_home / ".codex-global-state.json").write_text(
                json.dumps({"local-projects": {"study": {"rootPaths": [str(source_project)]}}}), encoding="utf-8"
            )
            package = root / "usb-package"
            with patch("codex_migration.package.require_apps_stopped"):
                export_package(source_home, package, [("StudyAssistant", source_project)])

            self.assertTrue((package / "launcher" / "RESTORE-WINDOWS.cmd").is_file())
            self.assertTrue((package / "launcher" / "RESTORE-MAC.command").is_file())
            runner = package / "toolkit" / "scripts" / "codex-migration.py"
            self.assertTrue(runner.is_file())
            bundled_help = subprocess.run([sys.executable, runner, "--help"], capture_output=True, text=True, check=False)
            self.assertEqual(bundled_help.returncode, 0, bundled_help.stderr)
            self.assertIn("one-click-restore", bundled_help.stdout)

            target_home = root / "target-codex"
            target_home.mkdir()
            target_projects = root / "restored-projects"
            with patch("codex_migration.restore.require_apps_stopped"):
                result = restore_everything(
                    package, target_codex_home=target_home, project_destination=target_projects
                )

            self.assertEqual(result["status"], "completed")
            self.assertTrue((target_projects / "StudyAssistant" / "main.py").is_file())
            state = json.loads((target_home / ".codex-global-state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["local-projects"]["study"]["rootPaths"], [str(target_projects / "StudyAssistant")])
            self.assertEqual(result["one_click"]["project_destination"], str(target_projects))

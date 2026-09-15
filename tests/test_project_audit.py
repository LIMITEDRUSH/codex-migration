import tempfile
import unittest
from pathlib import Path

from codex_migration.project_audit import audit_project


class ProjectAuditTests(unittest.TestCase):
    def test_non_git_folder_is_reported_without_writing(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "plain-project"
            project.mkdir()
            report = audit_project(project)
            self.assertEqual(report["project"], str(project))
            self.assertIn("repository", report["git"])

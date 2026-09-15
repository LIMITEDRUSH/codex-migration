import unittest

from codex_migration.mapping import map_path, parse_mapping
from codex_migration.rewrite import rewrite_structured_paths


class MappingTests(unittest.TestCase):
    def test_uses_longest_windows_prefix(self):
        mappings = [
            parse_mapping(r"C:\Users\Lenovo\Documents=D:\Documents"),
            parse_mapping(r"C:\Users\Lenovo\Documents\ChatGPT=E:\ChatGPT"),
        ]
        self.assertEqual(
            map_path(r"C:\Users\Lenovo\Documents\ChatGPT\MemoryRush", mappings),
            r"E:\ChatGPT\MemoryRush",
        )

    def test_rewrites_structured_paths_but_keeps_history(self):
        mappings = [parse_mapping(r"C:\Users\Lenovo=D:\Users\Limit")]
        original = {
            "cwd": r"C:\Users\Lenovo\Desktop\YEAR4",
            "rootPaths": [r"C:\Users\Lenovo\Documents"],
            "thread-workspace-root-hints": {"thread-id": r"C:\Users\Lenovo\Desktop\YEAR4"},
            "thread-writable-roots": {"thread-id": [r"C:\Users\Lenovo\Documents"]},
            "prompt-history": {"entries": [r"C:\Users\Lenovo\must-remain"]},
        }
        rewritten, count = rewrite_structured_paths(original, mappings)
        self.assertEqual(count, 4)
        self.assertEqual(rewritten["cwd"], r"D:\Users\Limit\Desktop\YEAR4")
        self.assertEqual(rewritten["rootPaths"], [r"D:\Users\Limit\Documents"])
        self.assertEqual(rewritten["thread-workspace-root-hints"]["thread-id"], r"D:\Users\Limit\Desktop\YEAR4")
        self.assertEqual(rewritten["thread-writable-roots"]["thread-id"], [r"D:\Users\Limit\Documents"])
        self.assertEqual(rewritten["prompt-history"], original["prompt-history"])

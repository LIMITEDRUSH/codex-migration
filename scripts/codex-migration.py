"""Run the project directly from a source checkout without installing it."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codex_migration.cli import main  # noqa: E402

raise SystemExit(main())

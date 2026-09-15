#!/bin/bash
set -u
ROOT="$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)"
CODEX_HOME="${HOME}/.codex"
if [ ! -d "$CODEX_HOME" ]; then
  echo "Codex home was not found at $CODEX_HOME. Start Codex once, fully quit it, then retry."
  exit 2
fi
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3.10 or newer is required. Install Python 3, then retry."
  exit 2
fi
volumes=()
for candidate in /Volumes/*; do
  [ -d "$candidate" ] && volumes+=("$candidate")
done
if [ "${#volumes[@]}" -ne 1 ]; then
  echo "Connect exactly one USB volume, then run this launcher again."
  exit 2
fi
OUTPUT="${volumes[0]}/Codex-Migration-Package-$(date +%Y%m%d-%H%M%S)"
exec python3 "$ROOT/scripts/codex-migration.py" export --codex-home "$CODEX_HOME" --output "$OUTPUT"

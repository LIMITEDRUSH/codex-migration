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

echo
echo "Migration scope: portable .codex data plus every project Codex currently registers."
echo "The following list is a review step only; project files are not read or copied yet."
if ! python3 "$ROOT/scripts/codex-migration.py" scope --codex-home "$CODEX_HOME"; then
  echo "Could not determine the Codex project scope. Resolve the reported missing path before exporting."
  exit 2
fi

extra_args=()
echo
echo "If a required folder was never opened as a Codex project, add it now as NAME=PATH."
echo "Press Return without typing anything when there are no more unregistered projects."
while true; do
  printf "Additional project (optional): "
  IFS= read -r extra
  [ -z "$extra" ] && break
  case "$extra" in
    *=*) extra_args+=(--project "$extra") ;;
    *) echo "Use a simple name and an existing path, for example: StudyAssistant=/Users/me/Projects/StudyAssistant" ;;
  esac
done

exec python3 "$ROOT/scripts/codex-migration.py" export --codex-home "$CODEX_HOME" --output "$OUTPUT" "${extra_args[@]}"

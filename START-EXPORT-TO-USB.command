#!/bin/bash
ROOT="$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)"
exec "$ROOT/scripts/Export-To-USB.sh"

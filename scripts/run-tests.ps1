$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = Join-Path $root 'src'
py -3 -m unittest discover -s (Join-Path $root 'tests') -v

param(
    [string]$UsbDrive
)

$ErrorActionPreference = 'Stop'

function Get-PythonCommand {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        return @{ Command = 'py'; Prefix = @('-3') }
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        return @{ Command = 'python'; Prefix = @() }
    }
    throw 'Python 3.10 or newer is required. Install Python, then run this launcher again.'
}

function Resolve-UsbRoot([string]$RequestedDrive) {
    $removable = @(Get-CimInstance Win32_LogicalDisk | Where-Object { $_.DriveType -eq 2 -and $_.DeviceID })
    if ($removable.Count -eq 0) {
        throw 'No removable USB drive was found. Insert the U disk and run this launcher again.'
    }
    if ($RequestedDrive) {
        $normalized = $RequestedDrive.Trim().TrimEnd('\').TrimEnd(':') + ':'
        $match = $removable | Where-Object { $_.DeviceID -eq $normalized }
        if (-not $match) {
            throw "Requested drive $normalized is not a removable USB drive."
        }
        return "$normalized\"
    }
    if ($removable.Count -eq 1) {
        return "$($removable[0].DeviceID)\"
    }
    $preferred = $removable | Where-Object { $_.DeviceID -eq 'G:' } | Select-Object -First 1
    if ($preferred) {
        return "$($preferred.DeviceID)\"
    }
    Write-Host 'More than one removable drive was found:'
    $removable | ForEach-Object { Write-Host "  $($_.DeviceID)  $($_.VolumeName)  $([math]::Round($_.FreeSpace / 1GB, 1)) GB free" }
    $selected = Read-Host 'Type the USB drive letter to use (for example G)'
    return Resolve-UsbRoot $selected
}

$codexHome = Join-Path $env:USERPROFILE '.codex'
if (-not (Test-Path -LiteralPath $codexHome -PathType Container)) {
    throw "Codex home was not found at $codexHome. Start Codex once first, then fully quit it and retry."
}

$usbRoot = Resolve-UsbRoot $UsbDrive
$packageName = 'Codex-Migration-Package-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
$output = Join-Path $usbRoot $packageName
$runner = Join-Path $PSScriptRoot 'codex-migration.py'
$python = Get-PythonCommand

Write-Host "Creating a self-contained Codex package at $output"
Write-Host 'Codex/ChatGPT must be fully closed. The migration tool will refuse to continue if it is running.'
$commandArguments = @()
$commandArguments += $python.Prefix
$commandArguments += @($runner, 'export', '--codex-home', $codexHome, '--output', $output)
& $python.Command @commandArguments
$code = $LASTEXITCODE
if ($code -eq 0) {
    Write-Host ''
    Write-Host "Done. Keep the entire folder on the USB drive: $output"
    Write-Host 'On the new computer, use launcher\RESTORE-WINDOWS.cmd or launcher/RESTORE-MAC.command inside that folder.'
}
exit $code

# Codex Migration: Quick Start

[中文说明](QUICKSTART_ZH.md)

## What it does

Codex Migration moves portable Codex Desktop data and complete project folders through a USB drive. It works between Windows and macOS and does not require OneDrive or another cloud service.

## Three steps

1. On the old computer, fully quit Codex, ChatGPT, and Codex CLI sessions. Insert a USB drive and run:

   ```text
   Windows: START-EXPORT-TO-USB.cmd
   macOS:   START-EXPORT-TO-USB.command
   ```

   Confirm the displayed USB drive before any data is written. If it is not the right drive, enter its Windows drive letter or its macOS `/Volumes/...` path.

2. Review the listed Codex projects. Add a folder that was never opened in Codex as `NAME=PATH`, or press Enter. Keep the generated `Codex-Migration-Package-<timestamp>` folder intact on the USB drive.

3. On the new computer, install and open Codex once, then fully quit it. In the USB package run:

   ```text
   Windows: launcher\RESTORE-WINDOWS.cmd
   macOS:   launcher/RESTORE-MAC.command
   ```

Projects restore under `Codex-Restored-Projects` in the new user’s home folder. Sign in to Codex again, open each restored project, and create a new task to confirm it works.

## How it stays safe

- Copies complete selected project roots instead of guessing individual files.
- Verifies the USB package with SHA-256 before restoring.
- Restores project files before activating remapped Codex state.
- Backs up an existing target `.codex` folder.
- Does not copy logins, cookies, keychain data, or API credentials.

Keep the source computer and USB package until every project passes verification.

# Safety and recovery

## Before every write

1. Close ChatGPT/Codex completely, including its tray/background process and Codex CLI sessions.
2. Run `inspect` and preserve its JSON report.
3. Run `verify` on the transferred package.
4. Run `restore` without `--apply` and review the reported mappings.
5. Keep the source machine and the package unchanged until target verification is complete.

The tool rejects known running desktop processes for write operations. That prevents the common failure mode where a running desktop app overwrites a repaired state file from memory.

## Credential boundary

`auth.json`, tokens, cookies, browser stores, keychains, secrets, locks, and volatile SQLite WAL/SHM files are excluded. A target computer must authenticate again. Package contents may still include source code, conversations, attachments, local paths, and logs; encrypt physical media and do not publish a package.

## Restore design

A restore never modifies the target by default. With `--apply --replace-existing`, it:

1. verifies the complete input manifest;
2. copies the current target Codex home to a timestamped sibling backup;
3. constructs the proposed target in a sibling staging directory;
4. applies only explicit structured path mappings;
5. checks every copied SQLite database with `PRAGMA quick_check`;
6. swaps the staged directory into place; and
7. retains the previous target and the full backup for manual rollback.

If a stage check fails, the live target is left untouched.

## Known desktop-state boundary

Codex Desktop stores durable conversation data and additional UI project state in separate locations. This tool copies both where present, but internal schemas can change. Treat a successful file restore as necessary, not sufficient: after reopening Codex, open each project folder and create a new task. If the app does not recognize a migrated project, preserve the reports and package rather than deleting or hand-editing conversation data.

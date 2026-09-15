# Codex Migration

`codex-migration` is a local-first, cross-platform migration and recovery toolkit for Codex Desktop data.

It was designed from an actual Windows profile migration: project files, local conversations, sessions, skills, plugins, SQLite state, attachments, and UI project mappings are related but **not the same thing**. Copying one of them alone is not a complete migration.

> This is an independent utility, not an OpenAI product. Codex's desktop storage schema can change. Always keep the source computer and an independent package until the target passes verification.

## What it does

- Inspects a Codex home without changing it.
- Creates a portable directory package with SHA-256 manifest verification.
- Excludes authentication and runtime lock files by default.
- Copies selected project folders separately from Codex state.
- Verifies a package before any restore.
- Produces a restore plan by default; `--apply` is required to write.
- Backs up the full destination Codex home before restoration.
- Applies explicit old-to-new path mappings only to known structured metadata fields and supported SQLite columns.
- Refuses write operations while known Codex/ChatGPT desktop processes are running.

## Non-goals and limits

- It does not copy `auth.json`, browser cookies, OS keychain data, API keys, or desktop credentials. Sign in again on the new computer.
- It does not modify project source files during path mapping.
- It does not rewrite historical conversation prose, shell commands, or tool output.
- Project registration is schema-dependent. After a cross-platform restore, open each restored project folder once in Codex and confirm that a new task can be created.
- It does not merge divergent target and source conversations. Restore into a fresh Codex installation, or explicitly choose `--replace-existing` after checking the plan.

## Requirements

- Python 3.10 or newer.
- Codex/ChatGPT Desktop and all Codex CLI sessions fully exited before `export --apply` or `restore --apply`.

No third-party Python dependencies are required.

## Quick start

On the source computer:

```powershell
python -m codex_migration inspect --codex-home $env:USERPROFILE\.codex
python -m codex_migration export --codex-home $env:USERPROFILE\.codex `
  --output G:\Codex-Migration-Package `
  --project StudyAssistant=C:\Users\Limit\Desktop\YEAR4
python -m codex_migration verify --package G:\Codex-Migration-Package
```

Transfer the entire package privately. On the target computer, install and launch Codex once, then fully quit it. Plan a restore first:

```bash
python -m codex_migration restore \
  --package /Volumes/USB/Codex-Migration-Package \
  --target-codex-home ~/.codex \
  --map 'C:\\Users\\Limit\\Desktop\\YEAR4=/Users/me/Documents/StudyAssistant'
```

Apply only after reviewing the plan and ensuring the target state can be replaced:

```bash
python -m codex_migration restore \
  --package /Volumes/USB/Codex-Migration-Package \
  --target-codex-home ~/.codex \
  --restore-projects-to ~/Documents/Codex-Restored-Projects \
  --map 'C:\\Users\\Limit\\Desktop\\YEAR4=/Users/me/Documents/StudyAssistant' \
  --replace-existing --apply
```

Then reopen Codex, sign in, open each restored project folder, create a fresh task, and run:

```bash
python -m codex_migration inspect --codex-home ~/.codex
```

## Package layout

```text
Codex-Migration-Package/
├── package.json                 # format and safety metadata
├── MANIFEST.sha256              # SHA-256 for every packaged file
├── codex-home/                  # portable, non-auth Codex profile data
├── projects/                    # only projects explicitly requested
└── reports/                     # inventory and restore reports
```

## Commands

| Command | Writes data? | Purpose |
| --- | --- | --- |
| `inspect` | No | Inventory sessions, databases, and project-state fields. |
| `export` | Yes, package only | Build a verified portable package. |
| `verify` | No | Recompute every manifest hash. |
| `restore` | No by default | Build a restore plan; `--apply` stages and replaces the target only after a full backup. |

Read [Safety and recovery](docs/SAFETY.md) and [Architecture](docs/ARCHITECTURE.md) before restoring data.

## Development

```powershell
python -m unittest discover -s tests -v
python -m codex_migration --help
```

## License

MIT. See [LICENSE](LICENSE).

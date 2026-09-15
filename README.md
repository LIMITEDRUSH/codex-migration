# Codex Migration

`codex-migration` is a local-first, cross-platform migration and recovery toolkit for Codex Desktop data.

It was designed from an actual Windows profile migration: project files, local conversations, sessions, skills, plugins, SQLite state, attachments, and UI project mappings are related but **not the same thing**. Copying one of them alone is not a complete migration.

> This is an independent utility, not an OpenAI product. Codex's desktop storage schema can change. Always keep the source computer and an independent package until the target passes verification.

## What it does

- Inspects a Codex home without changing it.
- Creates a self-contained, USB-first TAR package with SHA-256 manifest verification. It never assumes a cloud drive will resync data.
- Excludes authentication and runtime lock files by default.
- Automatically copies every existing project root registered by Codex, plus every extra project folder explicitly supplied with `--project`.
- Retains the conventional Codex desktop-state directory as a separate, non-auth **manual-only safety snapshot** when it exists; it is never blindly written over the target desktop state.
- Verifies a package before any restore.
- Produces a restore plan by default; `--apply` is required to write.
- Backs up the full destination Codex home before restoration.
- Applies explicit old-to-new path mappings only to known structured metadata fields and supported SQLite columns.
- Refuses write operations while known Codex/ChatGPT desktop processes are running.

## Non-goals and limits

- It does not copy `auth.json`, browser cookies, OS keychain data, API keys, or desktop credentials. Sign in again on the new computer.
- It copies every project currently registered by Codex by default. Add unregistered work with `--project NAME=PATH`; the package is complete only for those registered or explicitly supplied roots, not for arbitrary folders elsewhere on the computer.
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
  --project UnregisteredProject=C:\Users\Limit\Documents\UnregisteredProject
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
├── archives/                    # USB-safe single-file payloads; avoids exFAT small-file bloat
│   ├── codex-home.tar           # portable, non-auth Codex profile data
│   ├── projects/                # every registered/explicit project, byte-for-byte
│   └── desktop-state-safety.tar # optional, portable snapshot; never auto-applied
└── reports/                     # inventory and restore reports
```

## Commands

| Command | Writes data? | Purpose |
| --- | --- | --- |
| `inspect` | No | Inventory sessions, databases, and project-state fields. |
| `export` | Yes, package only | Build a verified self-contained USB package. Archive transport and desktop-state safety snapshot are defaults. |
| `verify` | No | Recompute every manifest hash. |
| `project-audit` | No | Check a restored project, Git HEAD/status, and worktree metadata. |
| `restore` | No by default | Build a restore plan; `--apply` stages and replaces the target only after a full backup. |

Read [Safety and recovery](docs/SAFETY.md), [Architecture](docs/ARCHITECTURE.md), the field-tested [migration lessons](docs/LESSONS_FROM_FIELD_MIGRATION.md), and the step-by-step [Chinese migration runbook](docs/RUNBOOK_ZH.md) before restoring data.

## Development

```powershell
python -m unittest discover -s tests -v
python -m codex_migration --help
```

## License

MIT. See [LICENSE](LICENSE).

# Codex Migration

[![English guide](https://img.shields.io/badge/Read-English-2563EB?style=for-the-badge)](docs/QUICKSTART_EN.md)
[![中文说明](https://img.shields.io/badge/阅读-中文说明-DC2626?style=for-the-badge)](docs/QUICKSTART_ZH.md)

Move a working Codex Desktop setup to another Windows or Mac computer with a USB drive. It packages portable Codex data and complete Codex project folders, verifies the package, restores files first, and then updates known project paths.

通过 U 盘将可工作的 Codex Desktop 环境迁移到另一台 Windows 或 Mac。它打包可迁移的 Codex 数据和完整项目文件夹，校验迁移包，先恢复文件，再更新已知项目路径。

**No cloud required · 不依赖云盘**  
**Windows ⇄ macOS · 支持 Windows 与 macOS 双向迁移**

## Start here / 从这里开始

| Old computer / 旧电脑 | New computer / 新电脑 |
| --- | --- |
| Fully quit Codex, insert a USB drive, then double-click `START-EXPORT-TO-USB.cmd` (Windows) or `START-EXPORT-TO-USB.command` (macOS). | Install and open Codex once, fully quit it, then run `launcher/RESTORE-WINDOWS.cmd` or `launcher/RESTORE-MAC.command` from the USB package. |

Choose a language for the full three-step guide: [English](docs/QUICKSTART_EN.md) · [中文](docs/QUICKSTART_ZH.md).

> This is an independent utility, not an OpenAI product. Codex's desktop storage schema can change. Always keep the source computer and an independent package until the target passes verification.

## What it does

- Inspects a Codex home without changing it.
- Creates a self-contained, USB-first TAR package with SHA-256 manifest verification. It never assumes a cloud drive will resync data.
- Excludes authentication and runtime lock files by default.
- Automatically copies every existing project root registered by Codex, plus every extra project folder explicitly supplied with `--project`.
- Shows the exact project-root coverage before one-click export, and writes `reports/coverage.json` into every USB package for later audit.
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
- Codex/ChatGPT Desktop and all Codex CLI sessions fully exited before export or `restore --apply`.

No third-party Python dependencies are required.

## 一键 U 盘迁移（推荐）

一次性前提：源电脑和目标电脑都要有 Python 3.10+；目标电脑还要先安装 Codex、启动一次后完全退出。无需 OneDrive，也不需要在新电脑重新下载本项目。

1. 源电脑插入 U 盘，完全退出 Codex/ChatGPT，双击项目根目录的 [START-EXPORT-TO-USB.cmd](START-EXPORT-TO-USB.cmd)（Mac 为 `START-EXPORT-TO-USB.command`）。它会自动选择唯一的 U 盘（Windows 多块时才询问盘符；优先 G:），并创建带时间戳的 `Codex-Migration-Package-*` 文件夹。
2. 导出器先列出 Codex 已登记项目；若有从未在 Codex 打开过、但也必须迁走的文件夹，可在同一窗口输入 `名称=路径` 补充。随后它收集可移植 `.codex` 数据、所有选定项目、额外桌面状态安全快照，并把恢复器一同写到 U 盘。缺失的已登记项目会使导出停止，避免漏迁移。
3. 新电脑安装并完全退出 Codex，插入 U 盘后双击迁移包内的：
   - Windows：`launcher\RESTORE-WINDOWS.cmd`
   - macOS：`launcher/RESTORE-MAC.command`
4. 恢复器自动校验哈希、备份目标 `.codex`、把项目写入用户主目录的 `Codex-Restored-Projects`（刻意避开可能被 OneDrive 重定向的 Documents；若同名已存在则使用带时间戳的新目录）、根据包内记录重写路径，并在状态中仍有失效项目路径时停止。
5. 打开 Codex 后重新登录；逐一打开恢复项目，并创建一个新任务验收。不要删除旧电脑、U 盘包或自动生成的备份，直到验收完成。

详细中文说明见 [一键迁移指南](docs/ONE_CLICK_ZH.md)。

## Advanced/manual commands

On the source computer:

```powershell
py .\scripts\codex-migration.py inspect --codex-home $env:USERPROFILE\.codex
py .\scripts\codex-migration.py export --codex-home $env:USERPROFILE\.codex `
  --output G:\Codex-Migration-Package `
  --project UnregisteredProject=C:\Users\Limit\Documents\UnregisteredProject
py .\scripts\codex-migration.py verify --package G:\Codex-Migration-Package
```

Transfer the entire package privately. On the target computer, install and launch Codex once, then fully quit it. Plan a restore first:

```bash
python -m codex_migration restore \
  --package /Volumes/USB/Codex-Migration-Package \
  --target-codex-home ~/.codex \
  --map 'C:\\Users\\Limit\\Desktop\\YEAR4=/Users/me/Codex-Restored-Projects/StudyAssistant'
```

Apply only after reviewing the plan and ensuring the target state can be replaced:

```bash
python -m codex_migration restore \
  --package /Volumes/USB/Codex-Migration-Package \
  --target-codex-home ~/.codex \
  --restore-projects-to ~/Codex-Restored-Projects \
  --map 'C:\\Users\\Limit\\Desktop\\YEAR4=/Users/me/Codex-Restored-Projects/StudyAssistant' \
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
├── launcher/                    # double-click restore launchers for Windows and macOS
├── toolkit/                     # self-contained Python runtime copied into this package
└── reports/                     # inventory and restore reports
```

## Commands

| Command | Writes data? | Purpose |
| --- | --- | --- |
| `inspect` | No | Inventory sessions, databases, and project-state fields. |
| `scope` | No | Show the registered and explicit project roots that an export will cover. |
| `export` | Yes, package only | Build a verified self-contained USB package. Archive transport and desktop-state safety snapshot are defaults. |
| `verify` | No | Recompute every manifest hash. |
| `project-audit` | No | Check a restored project, Git HEAD/status, and worktree metadata. |
| `restore` | No by default | Build a restore plan; `--apply` stages and replaces the target only after a full backup. |
| `one-click-restore` | Yes | Used by the bundled launcher; generates mappings from package metadata and restores after verification. |

Read [Safety and recovery](docs/SAFETY.md), [Architecture](docs/ARCHITECTURE.md), the field-tested [migration lessons](docs/LESSONS_FROM_FIELD_MIGRATION.md), and the step-by-step [Chinese migration runbook](docs/RUNBOOK_ZH.md) before restoring data.

## Development

```powershell
python -m unittest discover -s tests -v
python -m codex_migration --help
```

## License

MIT. See [LICENSE](LICENSE).

# Field migration lessons encoded in this tool

This project was hardened against failures observed in a real profile move. These are product constraints, not optional tips.

| Observed failure mode | Enforced design response |
| --- | --- |
| Copying hundreds of thousands of small files directly to an exFAT USB drive made capacity use explode. | The default is a small number of uncompressed PAX TAR payloads, with a pre-write free-space check. `--transport directory` is deliberately non-default. |
| A raw diff of a whole `.codex` tree reported tens of thousands of missing files even though durable conversations were present. | Authentication, caches, `.tmp`, sandbox/runtime folders, locks, WAL/SHM, and crash data are classified as volatile and excluded from portable payloads. Durable data is inspected separately. |
| UI project entries looked restored but a new task failed because a different state field still used an old absolute path. | The mapper and validator cover local project roots, per-thread workspace hints, writable roots, Electron saved roots, active roots, SQLite `cwd`, rollout paths, and project roots. |
| A quick repair script silently removed stale project records. | This tool never deletes unresolved project state. Restore stops by default until mappings are valid; an explicit override leaves a warning in the restore report. |
| Editing state while Codex was open was later overwritten by the running desktop process. | Every write operation fails closed if known Codex/ChatGPT processes cannot be checked or are still running. |
| Copying desktop credentials created unpredictable sign-in and security problems. | Authentication, browser stores, keychains, and secrets are never activated by a restore. The target signs in independently. |
| A package appeared to copy successfully but contained a corrupted or incomplete payload. | The manifest covers every packaged archive/report/metadata file and must verify before restore. TAR extraction rejects traversal, links, devices, and unexpected prefixes. |
| Cloud sync happened to mask an omitted folder on one machine. | Cloud storage is never assumed. The exporter includes every existing Codex-registered root and any explicit extra root in the USB package, and fails instead of silently omitting a registered root that is missing. |
| A migration required too many manual source-to-target mappings, causing avoidable omissions. | Every current package carries a compact copy of the recovery runtime and Windows/macOS launchers. The one-click restore derives mappings from recorded source project roots, while retaining target backups and refusing unresolved paths. |

The remaining boundary is Codex's evolving private storage schema. A successful restore is still followed by opening historical conversations, opening attachments, opening every project root, and creating a new task in each project before any original source or package is discarded.

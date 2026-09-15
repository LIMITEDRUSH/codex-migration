# Architecture

`codex-migration` has four safety layers:

```text
Inspect -> Export + manifest -> Verify + restore plan -> Staged restore + target verification
```

## Data classes

| Data | Treatment |
| --- | --- |
| Conversations, sessions, archived sessions, SQLite indexes | Portable profile data. |
| `.codex-global-state.json` and known project mappings | Portable but path-mapped only in structured fields. |
| Project files | Separate, explicit package payload; every selected byte is written to the USB package. |
| Skills/plugins/images | Portable profile data where present. |
| Auth, cookies, OS keys, locks/WAL/SHM | Excluded. |

`inspect` reports both total files and portable/volatile counts. Runtime cache differences are therefore visible but are not mistaken for loss of durable conversation or project data.

## Path mapping

Mappings use `OLD=NEW` and pick the longest matching old prefix. A mapping affects only structured fields such as `cwd`, `rollout_path`, `rootPaths`, workspace hints, writable roots, saved workspace roots, active workspace roots, and `workspace_by_cwd`. It deliberately excludes `prompt-history` and free-form message text.

SQLite rewriting is schema-probed. The tool updates `threads.cwd`, `threads.rollout_path`, and `project_roots.path` when they exist, plus JSON-valued policy columns only when they parse as JSON. Unrecognized schema is reported and preserved rather than guessed.

## Why projects are separate

Conversation history can point at a workspace but does not contain its source files. Every existing root in Codex's project registry is included automatically; unregistered roots must be added with `--project NAME=PATH`. Each selected root is archived as `archives/projects/NAME.tar`, with no cloud-sync assumption.

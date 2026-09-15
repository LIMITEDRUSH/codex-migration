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
| Project files | Separate, opt-in package payload. |
| Skills/plugins/images | Portable profile data where present. |
| Auth, cookies, OS keys, locks/WAL/SHM | Excluded. |

## Path mapping

Mappings use `OLD=NEW` and pick the longest matching old prefix. A mapping affects only structured fields such as `cwd`, `rootPaths`, `workspace_roots`, `path`, writable roots, and `workspace_by_cwd`. It deliberately excludes `prompt-history` and free-form message text.

SQLite rewriting is schema-probed. The tool updates a `threads.cwd` column when it exists and JSON-valued policy columns only when they parse as JSON. Unrecognized schema is reported and preserved rather than guessed.

## Why projects are separate

Conversation history can point at a workspace but does not contain its source files. The source project must be explicitly added with `--project NAME=PATH`; only then is it copied under `projects/NAME`. This makes package size and source-code inclusion an explicit decision.

# Codex Migration — Quick Start / 快速开始

## What it is / 这是什么

**English.** Codex Migration is a local-first tool for moving a working Codex Desktop setup between computers. It packages portable Codex state and the complete folders of projects registered in Codex onto a USB drive. It does not use or require OneDrive, iCloud, or another cloud drive.

**中文。** Codex Migration 是一个本地优先的 Codex Desktop 迁移工具。它把可迁移的 Codex 状态以及 Codex 已登记项目的完整文件夹打包到 U 盘；不使用、也不依赖 OneDrive、iCloud 或其他云盘。

## Use it in three steps / 三步使用

1. **Export on the old computer / 在旧电脑导出**

   Fully quit Codex, ChatGPT, and Codex CLI sessions. Insert a USB drive and double-click:

   ```text
   Windows: START-EXPORT-TO-USB.cmd
   macOS:   START-EXPORT-TO-USB.command
   ```

   The launcher lists every project currently registered by Codex. Add any needed folder that was never opened in Codex as `NAME=PATH`; otherwise press Enter.

   完全退出 Codex、ChatGPT 和 Codex CLI，插入 U 盘后双击对应启动器。它会列出 Codex 已登记的全部项目。若某个必须迁移的文件夹从未在 Codex 打开过，输入 `名称=路径`；否则直接按 Enter。

2. **Move the complete package / 带走整个迁移包**

   Keep the generated `Codex-Migration-Package-<timestamp>` folder intact on the USB drive. Do not copy only one TAR file from it.

   保留 U 盘生成的整个 `Codex-Migration-Package-<时间戳>` 文件夹，不要只复制其中一个 TAR 文件。

3. **Restore on the new computer / 在新电脑恢复**

   Install and launch Codex once, then fully quit it. On the USB package, double-click:

   ```text
   Windows: launcher\RESTORE-WINDOWS.cmd
   macOS:   launcher/RESTORE-MAC.command
   ```

   Projects restore by default to `Codex-Restored-Projects` under the new user’s home folder. Reopen Codex, sign in again, open each project, and create one new task as acceptance testing.

   项目默认恢复到新用户主目录下的 `Codex-Restored-Projects`。随后打开 Codex、重新登录、逐一打开项目并创建一个新任务进行验收。

## How it works / 工作原理

| Step / 步骤 | English | 中文 |
| --- | --- | --- |
| Discover / 发现 | Reads Codex’s registered project roots. | 读取 Codex 已登记的项目根目录。 |
| Package / 打包 | Copies each selected root in full and portable Codex state into USB-safe TAR archives. | 完整复制每个选定项目根目录和可移植 Codex 状态，并写入适合 U 盘的 TAR 归档。 |
| Verify / 校验 | Creates a SHA-256 manifest and verifies it before restore. | 生成 SHA-256 清单，并在恢复前校验。 |
| Stage / 暂存 | Restores files into staging locations before activating Codex state. | 先恢复到暂存位置，再激活 Codex 状态。 |
| Remap / 重映射 | Rewrites known structured project/workspace paths to the new operating system’s paths. | 将已知的结构化项目/工作区路径重写为新系统路径。 |
| Protect / 保护 | Backs up the target `.codex` and stops if known paths remain missing. | 备份目标 `.codex`；若已知路径仍缺失则停止。 |

## Important boundaries / 重要边界

**English.** This is not a credential-cloning tool. It deliberately excludes `auth.json`, browser cookies, keychain data, locks, WAL/SHM files, and runtime caches. Sign in again on the new computer. It copies only Codex-registered projects and explicitly added roots; it does not guess arbitrary folders mentioned in conversations.

**中文。** 这不是凭据克隆工具。它会刻意排除 `auth.json`、浏览器 Cookie、系统钥匙串数据、锁文件、WAL/SHM 文件和运行时缓存；请在新电脑重新登录。它只复制 Codex 已登记项目和显式添加的根目录，不会猜测对话中偶然提到的任意文件夹。

## Before deleting anything / 删除前

**English.** Keep the source computer, USB package, and automatically created backup until every restored project opens, its files are usable, and a new task can be created.

**中文。** 在每个恢复项目都能打开、文件可用且能新建任务之前，请保留旧电脑、U 盘迁移包和自动生成的备份。

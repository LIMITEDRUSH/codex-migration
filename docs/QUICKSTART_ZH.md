# Codex Migration：快速开始

[English guide](QUICKSTART_EN.md)

## 它能做什么

Codex Migration 通过 U 盘迁移可携带的 Codex Desktop 数据和完整项目文件夹。支持 Windows 与 macOS 互迁，不依赖 OneDrive 或其他云盘。

## 三步完成

1. 在旧电脑完全退出 Codex、ChatGPT 和 Codex CLI，插入 U 盘后运行：

   ```text
   Windows：START-EXPORT-TO-USB.cmd
   macOS：   START-EXPORT-TO-USB.command
   ```

   写入前会显示识别到的 U 盘并要求确认。若不是正确的盘，输入 Windows 盘符或 macOS 的 `/Volumes/...` 卷路径。

2. 确认窗口列出的 Codex 项目。若有从未在 Codex 打开过、但也要迁移的目录，输入 `名称=路径`；否则直接按 Enter。保留 U 盘生成的整个 `Codex-Migration-Package-时间戳` 文件夹。

3. 在新电脑安装并打开 Codex 一次，然后完全退出。在 U 盘迁移包中运行：

   ```text
   Windows：launcher\RESTORE-WINDOWS.cmd
   macOS：   launcher/RESTORE-MAC.command
   ```

项目会恢复到新用户主目录下的 `Codex-Restored-Projects`。重新登录 Codex，逐一打开恢复项目，并创建一个新任务确认可继续工作。

## 为什么安全

- 完整复制选定项目根目录，不猜测单独文件。
- 恢复前用 SHA-256 校验 U 盘迁移包。
- 先恢复项目文件，再激活已重映射的 Codex 状态。
- 自动备份已有的目标 `.codex`。
- 不复制登录状态、Cookie、钥匙串数据或 API 凭据。

在所有项目均已验收前，请保留旧电脑和 U 盘迁移包。

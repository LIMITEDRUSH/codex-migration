# 一键 U 盘迁移指南

这个流程的目标是：源电脑双击一次导出，新电脑双击一次恢复。它不依赖 OneDrive，同一 U 盘包包含数据、校验清单和恢复工具。

## 首次准备

- 两台电脑安装 Python 3.10 或更高版本。
- 新电脑安装 Codex 并启动一次，再从菜单栏、系统托盘和所有 CLI 终端彻底退出。
- 使用空间足够的 U 盘；导出器会在写入前预估空间，空间不够会停止。

## 源电脑：双击导出

1. 插入 U 盘，关闭 Codex/ChatGPT 和所有 Codex CLI。
2. 双击项目下载目录中的 `START-EXPORT-TO-USB.cmd`（macOS 源端使用 `START-EXPORT-TO-USB.command`）。程序会先展示识别到的 U 盘并询问是否使用；若不是目标盘，输入 Windows 盘符（如 `G`）或 macOS 卷路径（如 `/Volumes/USB-DATA`）后再次确认。
3. 程序先列出 Codex 注册的实际项目路径。若有从未在 Codex 打开过、但也必须迁移的目录，在窗口中输入 `名称=完整路径`；没有就直接按 Enter。Windows 和 macOS 的源端一键启动器都执行同一确认步骤。随后它收集 `.codex`、每个选定项目和可移植桌面状态。
4. 完成时 U 盘上会出现 `Codex-Migration-Package-时间戳`。保留整个文件夹，不能只复制其中某个 tar 文件。包内 `reports/coverage.json` 是验收清单：它列出已包含的项目根目录及其文件数/归档大小，也明确说明未登记且未手工加入的目录不会被猜测或复制。

## 新电脑：双击恢复

1. 安装 Codex 并完全退出。
2. 在 U 盘迁移包内双击：Windows 的 `launcher\RESTORE-WINDOWS.cmd`，或 macOS 的 `launcher/RESTORE-MAC.command`。
3. 运行时自动执行：验证哈希 → 备份现有 `.codex` → 解包项目 → 按包内源路径自动生成映射 → 验证 SQLite 和项目路径 → 切换恢复结果。
4. 项目默认放在用户主目录的 `Codex-Restored-Projects`，刻意避开 Windows 上可能被 OneDrive 重定向的 Documents。如果该位置已有本迁移包的同名项目，恢复器会改用带时间戳的新目录，绝不覆盖现有项目源码。
5. 重新登录 Codex，打开每个项目并创建一个新任务。恢复报告位于 `~/.codex/codex-migration-restore-report.json`。

## 不会自动做的事

- 不复制或激活登录凭据、浏览器 Cookies、Keychain/系统凭据或 API 密钥；新电脑必须重新登录。
- 不删除失效项目记录；若自动映射后仍有路径不存在，恢复会停止并保留原目标状态和备份。
- 不合并两个已独立使用过的 Codex 配置；目标的原配置会保留时间戳备份。

如果双击后提示 Python 不存在，安装 Python 3.10+ 后重新双击同一个启动器即可。若 macOS 阻止 `.command` 文件，右键选择“打开”；必要时在终端运行 `chmod +x /Volumes/<U盘名>/<迁移包>/launcher/RESTORE-MAC.command` 后再双击。

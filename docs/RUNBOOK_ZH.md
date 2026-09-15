# 跨电脑 Codex 迁移运行手册

适用：Windows→Mac、Mac→Windows、Windows→Windows。目标是迁移本地 Codex 对话、会话、项目文件和可移植设置，并在新设备上能继续工作。

## 阶段 0：冻结源端

1. 关闭 ChatGPT/Codex 主窗口，并从系统托盘/菜单栏彻底退出。
2. 关闭所有 Codex CLI 终端。
3. 不要在 `.codex` 正在写入时复制 SQLite 文件；WAL/SHM 和锁文件不会被打包。
4. 保存源端的 `inspect` 报告，不删除旧设备上的任何数据。

```powershell
python scripts\codex-migration.py inspect `
  --codex-home $env:USERPROFILE\.codex `
  --report source-inspection.codex-migration-report.json
```

## 阶段 1：生成迁移包

Codex 对话数据和项目源码是两类不同对象。每个需要继续使用的项目都必须显式加入 `--project`。

```powershell
python scripts\codex-migration.py export `
  --codex-home $env:USERPROFILE\.codex `
  --output G:\Codex-Migration-Package `
  --project StudyAssistant=C:\Users\Limit\Desktop\YEAR4

python scripts\codex-migration.py verify --package G:\Codex-Migration-Package
```

迁移包会排除登录状态和运行期文件。登录新设备是正常且必须的步骤。

## 阶段 2：传输与完整性验证

1. 复制整个 `Codex-Migration-Package`，不要只复制其中的 `sessions` 或 SQLite。
2. 在目标设备再次运行 `verify`；任何 hash 不匹配都停止恢复并重新传输。
3. 若使用 OneDrive，确认所有目标项目文件均是本地可用状态，而不是仅有云端占位符。

## 阶段 3：目标设备恢复

1. 安装 Codex 并启动一次，让它创建本地配置。
2. 再次完整退出 Codex。
3. 先生成计划。Windows 源路径应明确映射到 Mac 上实际存在的新项目目录。

```bash
python scripts/codex-migration.py restore \
  --package /Volumes/USB/Codex-Migration-Package \
  --target-codex-home ~/.codex \
  --restore-projects-to ~/Documents/Codex-Restored-Projects \
  --map 'C:\\Users\\Limit\\Desktop\\YEAR4=/Users/me/Documents/Codex-Restored-Projects/StudyAssistant' \
  --report restore-plan.codex-migration-report.json
```

确认计划中的包 hash 为 `ok`、目标目录正确、路径映射合理后，才加入 `--replace-existing --apply`。

## 阶段 4：验收

恢复完成不等于桌面端已经识别所有项目。依次验证：

1. 启动 Codex 并重新登录。
2. 确认重要历史对话能打开，附件能打开。
3. 在每个恢复项目中用桌面端重新打开其真实文件夹。
4. 为每个项目创建一个新的测试任务，确认不再显示“项目文件夹已被删除或移动”。
5. 再运行 `inspect`，检查 SQLite `quick_check` 和 `stale_project_roots`。

## 失败恢复原则

- 不要在 Codex 运行时手动编辑 `.codex-global-state.json`；运行中的应用可能以内存中的旧状态覆盖修复结果。
- 不要把旧设备的 `auth.json`、浏览器 Cookies 或 Keychain 复制到新设备。
- 不要仅根据 UI 中“聊天出现”判断完成；还要验证项目文件、文件链接、对话和新任务创建。
- 恢复操作保留目标的时间戳备份和被替换目录。没有完成阶段 4 前，不要删除旧电脑、U 盘迁移包或这些备份。

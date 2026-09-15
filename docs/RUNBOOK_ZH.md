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

Codex 对话数据和项目源码是两类不同对象。默认会自动加入 Codex 已登记且在本机存在的全部项目；未登记但也要迁移的目录再显式加入 `--project`。工具不假定 OneDrive、iCloud 或任何云盘会同步：指定的 Codex 数据和项目会全部写入 U 盘迁移包。

```powershell
python scripts\codex-migration.py export `
  --codex-home $env:USERPROFILE\.codex `
  --output G:\Codex-Migration-Package `
  --project UnregisteredProject=C:\Users\Limit\Documents\UnregisteredProject

python scripts\codex-migration.py verify --package G:\Codex-Migration-Package
```

迁移包会排除登录状态和运行期文件。登录新设备是正常且必须的步骤。若系统中存在常规 Codex 桌面状态目录，工具还会将其以 **仅供人工核对的安全快照** 写入 U 盘；恢复不会自动覆盖目标端该目录。

## 阶段 2：传输与完整性验证

1. 保留整个 `Codex-Migration-Package` 在 U 盘，不要只复制其中的 `sessions`、SQLite 或单个 tar 文件。默认 archive 格式将大量小文件装进少量 tar 文件，避免 exFAT 分配单元造成容量暴涨。
2. 在目标设备再次运行 `verify`；任何 hash 不匹配都停止恢复并重新传输。
3. 确认清单列出了所有自动发现的已登记项目，并为未登记但必须继续使用的目录补充 `--project`；未登记且未显式加入的目录不会从云端补取。

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
6. 对每个 Git 项目运行 `python scripts/codex-migration.py project-audit --project <项目目录>`，确认 HEAD、工作区状态和 `git worktree` 元数据可读取。

## 失败恢复原则

- 不要在 Codex 运行时手动编辑 `.codex-global-state.json`；运行中的应用可能以内存中的旧状态覆盖修复结果。
- 不要把旧设备的 `auth.json`、浏览器 Cookies 或 Keychain 复制到新设备。
- 不要仅根据 UI 中“聊天出现”判断完成；还要验证项目文件、文件链接、对话和新任务创建。
- 不要把“云盘目录存在”当作迁移完成证据；本工具以 U 盘包的 `verify` 和目标端实际打开文件为准。
- 恢复操作保留目标的时间戳备份和被替换目录。没有完成阶段 4 前，不要删除旧电脑、U 盘迁移包或这些备份。

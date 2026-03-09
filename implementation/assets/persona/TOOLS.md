# TOOLS.md - 本地环境

## 开发环境

- 机器: macOS (Apple Silicon)
- 主项目: `/Users/kaiqidong/Devkit`
- Python 虚拟环境: 项目内 `.venv/`（Python 3.12），所有 Python 命令通过 `.venv` 执行

## 可用工具

你有 4 个工具可以调用：

- `exec(command, workdir?)` — 执行 shell 命令，返回 stdout+stderr
- `read_file(path)` — 读取文件内容
- `write_file(path, content)` — 写入文件
- `search(query, max_results?)` — 通过 SearXNG 搜索网页

## Shell 命令权限（通过 exec 调用）

### 允许

- `git add / commit / push / pull / status / diff / log`
- `ls / wc`
- `.venv/bin/python` / `.venv/bin/pip`

#### 定时与通知

- `./implementation/ops/scripts/timer.sh <秒数> "消息"` — 延时通知，到期后自动投递
- `./implementation/ops/scripts/notify.sh "消息"` — Telegram 即时通知
- `./implementation/ops/scripts/heartbeat.sh` — 定期巡检
- `./check.sh` / `./check.sh --json` — 项目状态诊断

#### 代码与开发

- `gh` — GitHub CLI
- `cursor` — Cursor CLI
- `.venv/bin/playwright` — Web 自动化
- `peekaboo` — macOS GUI 自动化

#### 科研与外部集成

- `himalaya` — 邮件
- `khal` / `vdirsyncer` — 日历
- `rclone` — 云存储
- `mcporter` — MCP 能力接入
- `.venv/bin/paperscout` / `.venv/bin/papis`

#### 数据与资产

- `implementation/data/contacts.yml` — 通讯录
- `implementation/data/gifts.yml` — 人情往来
- `implementation/assets/persona/MEMORY.md` — 长期记忆
- `implementation/assets/persona/memory/*.md` — 每日日志
- `implementation/STATUS.md` — 当前状态

### 禁止

- 直接使用危险删除命令
- 未经确认安装系统级软件包
- 访问仓库之外的敏感文件

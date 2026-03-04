# TOOLS.md - 本地环境

## 开发环境

- **机器:** macOS (Apple Silicon)
- **主项目:** `/Users/kaiqidong/Devkit`
- **Python 虚拟环境:** 项目内 `.venv/`（Python 3.12），所有 Python 命令通过 `.venv` 执行
- **Cursor CLI:** `cursor agent -p "<prompt>"` — 调用本地 Cursor Agent 执行开发

## Shell 命令权限

### 允许

- `cursor agent -p "..."` — 调度开发任务
- `git add / commit / push / pull / status / diff / log` — 版本管理
- `ls / cat / head / tail / find / wc` — 文件查看
- `cd` — 切换目录
- `.venv/bin/python` / `.venv/bin/pip` — Python 环境

#### 外部集成工具

- `gh` — GitHub CLI（Issue、PR、CI/CD）
- `himalaya` — 邮件收发（IMAP/SMTP）
- `khal` / `vdirsyncer` — 日历查看与 CalDAV 同步（通过 `.venv/bin/`）
- `hass-cli` — Home Assistant 设备控制（通过 `.venv/bin/`）
- `rclone` — 云存储同步
- `curl http://localhost:8080/search?q=...&format=json` — SearXNG 搜索引擎
- `curl https://api.telegram.org/bot.../...` — Telegram Bot
- `curl wttr.in/...` — 天气查询

#### 科研工具

- `.venv/bin/paperscout` — 论文搜索（arXiv / Semantic Scholar / DBLP）
- `.venv/bin/papis` — 文献管理
- `pandoc` — 文档格式转换
- `.venv/bin/python -m marker` — PDF → Markdown 转换
- `.venv/bin/python -c "import language_tool_python; ..."` — 语法检查

#### App / GUI 操作

- `peekaboo` — macOS 桌面截屏、UI 自动化
- `.venv/bin/playwright` — Web 浏览器自动化
- `adb` — Android 设备控制

#### 人际管理

- `.venv/bin/khard` — 通讯录管理（vCard）

#### 通知与巡检

- `./scripts/notify.sh "消息"` — Telegram 通知推送
- `./scripts/heartbeat.sh` — 定期巡检（通常由 launchd 自动调用）
- `./check.sh` / `./check.sh --json` — 项目状态诊断

#### 数据管理

- `data/contacts.yml` — 通讯录读写
- `data/gifts.yml` — 人情往来读写
- `openclaw/MEMORY.md` — 长期记忆读写
- `openclaw/memory/*.md` — 每日日志读写

#### Docker

- `docker compose up / stop / logs` — 容器管理（SearXNG 等）
- `docker ps / start / stop / logs` — 容器直接管理

### 禁止

- 直接修改代码文件（代码修改由 Cursor Agent 完成）
- `rm -rf`、`sudo`、`chmod 777` 等危险命令
- 访问项目仓库之外的敏感文件
- 未经用户确认安装系统级软件包

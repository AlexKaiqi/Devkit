# TOOLS.md - 本地环境

## 开发环境

- **机器:** macOS (Apple Silicon)
- **主项目:** `/Users/kaiqidong/Devkit`
- **Python 虚拟环境:** 项目内 `.venv/`（Python 3.12），所有 Python 命令通过 `.venv` 执行

## 可用工具

你有 4 个工具可以调用：

- `exec(command, workdir?)` — 执行 shell 命令，返回 stdout+stderr
- `read_file(path)` — 读取文件内容
- `write_file(path, content)` — 写入文件
- `search(query, max_results?)` — 通过 SearXNG 搜索网页

## Shell 命令权限（通过 exec 调用）

### 允许

- `git add / commit / push / pull / status / diff / log` — 版本管理
- `ls / cat / head / tail / find / wc` — 文件查看
- `.venv/bin/python` / `.venv/bin/pip` — Python 环境

#### MCP 工具（通过 mcporter）— A 股数据

调用格式：`mcporter call akshare-one-mcp.<工具名> --args '<JSON参数>'`

- `mcporter call akshare-one-mcp.get_hist_data --args '{"symbol":"600519","interval":"day","recent_n":10}'` — 历史 K 线（支持 minute/hour/day/week/month/year）
- `mcporter call akshare-one-mcp.get_financial_metrics --args '{"symbol":"600519","recent_n":3}'` — 核心财务指标
- `mcporter call akshare-one-mcp.get_balance_sheet --args '{"symbol":"600519","recent_n":3}'` — 资产负债表
- `mcporter call akshare-one-mcp.get_income_statement --args '{"symbol":"600519","recent_n":3}'` — 利润表
- `mcporter call akshare-one-mcp.get_cash_flow --args '{"symbol":"600519","recent_n":3}'` — 现金流量表
- `mcporter call akshare-one-mcp.get_news_data --args '{"symbol":"600519"}'` — 个股新闻
- `mcporter call akshare-one-mcp.get_inner_trade_data --args '{"symbol":"600519"}'` — 内幕交易
- `mcporter call akshare-one-mcp.get_time_info --args '{}'` — 当前时间与最近交易日
- `mcporter list` — 列出所有可用 MCP 服务器

股票代码格式：纯数字，如 `600519`（茅台）、`000001`（平安银行）、`300750`（宁德时代）。
当用户询问股票相关信息时，**直接调用上述命令**获取数据，不要说"无法查询"。
最近股价可用 `get_hist_data` + `recent_n=1` 获取最新交易日的开高低收。

**数据源注意**：`get_hist_data` 默认 eastmoney 数据源可能不稳定，沪市股票（6开头）优先加 `"source":"sina"`；如果失败，可不指定 source 或换 `"source":"eastmoney_direct"` 重试。
财务数据（`get_financial_metrics`、`get_balance_sheet`、`get_income_statement`、`get_cash_flow`）不受数据源影响，可直接调用。

#### 外部集成工具

- `gh` — GitHub CLI（Issue、PR、CI/CD）
- `himalaya` — 邮件收发（IMAP/SMTP）
- `khal` / `vdirsyncer` — 日历查看与 CalDAV 同步（通过 `.venv/bin/`）
- `hass-cli` — Home Assistant 设备控制（通过 `.venv/bin/`）
- `rclone` — 云存储同步
- `curl 'http://localhost:8080/search?q=关键词&format=json'` — SearXNG 搜索引擎（**URL 必须用单引号包裹**，防止 zsh 解析 `?` 和 `&`）
- `curl https://api.telegram.org/bot.../...` — Telegram Bot
- `curl 'wttr.in/城市名'` — 天气查询

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

#### 定时通知（⚠️ 唯一方式）

- `./scripts/timer.sh <秒数> "到期后发送的消息"` — **延时通知，到期自动推送到 Telegram**
  - 示例: exec `./scripts/timer.sh 60 '主人，1分钟到了'` — 60 秒后推送
  - 示例: exec `./scripts/timer.sh 600 '该开会了'` — 10 分钟后推送
  - 不阻塞当前 turn，立即返回 timer_id
  - ❌ **禁止用 `sleep`**（会阻塞对话）

#### 即时通知与巡检

- `./scripts/notify.sh "消息"` — Telegram 即时通知推送（立即发送，非延时）
- `./scripts/heartbeat.sh` — 定期巡检（通常由 launchd 自动调用）
- `./check.sh` / `./check.sh --json` — 项目状态诊断

#### 数据管理

- `data/contacts.yml` — 通讯录读写
- `data/gifts.yml` — 人情往来读写
- `persona/MEMORY.md` — 长期记忆读写
- `persona/memory/*.md` — 每日日志读写

#### Docker

- `docker compose up / stop / logs` — 容器管理（SearXNG 等）
- `docker ps / start / stop / logs` — 容器直接管理

### 禁止

- 直接修改代码文件（代码修改由 Cursor Agent 完成）
- `rm -rf`、`sudo`、`chmod 777` 等危险命令
- 访问项目仓库之外的敏感文件
- 未经用户确认安装系统级软件包

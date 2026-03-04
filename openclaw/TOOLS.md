# TOOLS.md - 本地环境

## 开发环境

- **机器:** macOS (Apple Silicon)
- **主项目:** `/Users/kaiqidong/workspace/Devkit`
- **Python 虚拟环境:** 项目内 `.venv/`，所有 Python 命令通过 `.venv` 执行
- **Cursor CLI:** `cursor agent -p "<prompt>"` — 调用本地 Cursor Agent 执行开发

## Shell 命令权限

### 允许

- `cursor agent -p "..."` — 调度开发任务
- `git add / commit / push / pull / status / diff / log` — 版本管理
- `ls / cat / head / tail / find / wc` — 文件查看
- `cd` — 切换目录
- `.venv/bin/python` / `.venv/bin/pip` — Python 环境

### 禁止

- 直接修改代码文件（代码修改由 Cursor Agent 完成）
- `rm -rf`、`sudo`、`chmod 777` 等危险命令
- 访问项目仓库之外的敏感文件
- 安装系统级软件包

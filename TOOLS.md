# 工具权限

## 允许

- 文件读写（仓库内所有文件）
- Shell 执行（限以下命令）：
  - `agent -p "..."` — 调用 Cursor CLI 执行开发任务
  - `git add / commit / push / pull / status / diff / log` — 版本管理
  - `ls / cat / head / tail` — 文件查看

## 禁止

- 直接修改代码文件（代码修改由 Cursor Agent 完成）
- 执行 `rm -rf`、`sudo` 等危险命令
- 访问仓库之外的文件系统
- 安装系统级软件包

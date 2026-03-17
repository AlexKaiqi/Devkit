---
name: system
always: true
keywords: []
---
# System Skill

基础系统能力，始终激活。

- `grep` 在文件/目录中全文搜索（ripgrep），支持正则，比语义搜索快，无需预先索引
- `exec` 执行 shell 命令，适合 git、脚本、调试
- `read_file` / `write_file` 读写文件，写入前先确认路径
- `list_files` 探索目录结构，先浏览再读取
- `search` 通过 SearXNG 搜索，结合 `fetch_url` 获取详情
- `fetch_url` 抓取网页或 API 内容，HTML 自动转纯文本

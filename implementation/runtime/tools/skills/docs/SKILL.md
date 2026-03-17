---
name: docs
always: false
keywords: [文档, 文件里, 合同, pdf, 报告, 材料, 找一下, 里面写的, 里面说的, 搜索文档, 文档搜索, 查一下文档, 这份, 那份, 读取文档, 文档内容, 知识库]
---
# Docs Skill

本地文档语义搜索能力（基于 LlamaIndex + Qwen3 Embedding）。

- `docs_index(path)` — 索引一个文件或目录（支持 PDF/TXT/MD/DOCX）
- `docs_search(query, top_k=5)` — 语义搜索，返回最相关片段
- `docs_list()` — 列出已索引的文档

使用场景：
- "帮我在上个月的合同里找付款条款"
- "这份报告里有没有提到风险"
- "索引一下 ~/Documents 下的 PDF"

索引持久化到 `implementation/runtime/data/docs_index/`，重启后无需重新索引。

---
name: memory
always: false
keywords: [记住, 记一下, 备忘, 笔记, 记录, 别忘了, 想起来, 记得, 提醒我记, 保存, note, remember, recall, 查一下记录, 之前说过, 我说过, 待办, 提醒自己, 忘了, 查一下]
---
# Memory Skill

快速记录与检索能力。

- `note(content, category?)` — 追加到今日日志（`memory/YYYY-MM-DD.md`），轻量快速
- `remember(content)` — 追加到 `MEMORY.md`，用于长期保留的事实、偏好、经验教训
- `recall(query)` — 全文搜索 memory 目录和 MEMORY.md，返回相关条目

使用规范：
- 用户说"帮我记一下"→ 判断是否长期：是则 `remember`，否则 `note`
- 用户说"之前……来着"→ 先 `recall` 再回答
- `remember` 条目格式：`- [YYYY-MM-DD] <内容>`
- `note` 自动带时间戳，category 可选（如 idea/todo/log）

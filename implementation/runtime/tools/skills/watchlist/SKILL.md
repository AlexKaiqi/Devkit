---
name: watchlist
always: false
keywords: [监控, 盯着, 订阅, 关注, 提醒我, watchlist, 有新消息, 有更新, 留意, 跟踪]
---
# Watchlist Skill

信息订阅与变更监控能力。

- `watch_add(topic, query, interval_hours=24)` — 添加监控项，返回 watch_id
- `watch_list()` — 列出所有当前订阅
- `watch_remove(watch_id)` — 删除指定订阅

使用场景：
- 用户说"帮我盯着XXX""有更新提醒我""订阅YYY消息"时调用 `watch_add`
- 用户说"我有哪些订阅"时调用 `watch_list`
- 用户说"取消对XXX的监控"时调用 `watch_remove`

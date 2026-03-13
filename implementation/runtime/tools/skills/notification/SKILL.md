---
name: notification
always: false
keywords: [通知, 提醒, 推送, notify, remind, 告知, 消息, 催, 提示, 定时, 到时, 稍后, 之后, 分钟后, 小时后]
---
# Notification Skill

通知与提醒能力。

- `notify` 立即推送通知（Telegram + Web Push 双渠道），urgent=true 跳过静默时段
- `remind` 设置延时提醒，支持相对时间（'5m'/'2h'/'1d'）或绝对时间（'YYYY-MM-DD HH:MM' CST）
- 重要事项推送后，记录在 MEMORY.md

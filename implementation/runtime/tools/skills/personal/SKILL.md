---
name: personal
always: false
keywords: [联系人, 日历, 日程, 生日, 通讯录, contacts, schedule, 约, 会议, 安排, 明天, 今天, 本周, 下周, 时间, 提前, 上次, 最近, 之前, 后天, 大后天, 下下周, 月底, 月初, 几点, 什么时候]
---
# Personal Skill

个人信息管理能力。

- 所有日程使用 `schedule`（本地 JSON），这是唯一的日程工具
- 新建事项若有时间约束，`schedule add` 和 `remind` 应同时调用
- `contacts` 读写本地通讯录（contacts.yml），支持 list/show/add/update/birthdays

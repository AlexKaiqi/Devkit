# 决策：事件与通知

## 决策

- 延时任务、主动提醒和任务续作统一通过事件系统承载。
- 异步结果优先回到原始会话；如需外部回报，可通过 Telegram 等可选通知渠道投递。
- runtime 发布意图，事件系统负责等待和回投。

## 原因

- 避免长时间阻塞主对话。
- 让定时器、回调和续作共享同一套基础设施。

---

## 扩展决策：语义意图（intent）字段（2026-03-16）

### 背景

现有提醒系统以**触发机制**（cron/once）为数据模型，缺乏**语义意图**层：
- 农历节日、节气无法用 cron 表达（每年公历日期不同）
- ops.html 只能展示 cron 表达式，无法体现"这是中秋节提醒"的语义
- 机制变更时语义信息丢失

### 决策：两套互补机制并存

```
EventBus (现有)
  └── intent: once      → ⏱ 一次性
  └── intent: recurring → 🔄 周期（cron）

CalendarChecker (新增，仿 WatchlistChecker)
  └── intent: holiday   → 🏮 内置节日（按农历查表）
  └── intent: lunar_date → 🌙 用户自定义农历日
  └── 每60分钟扫一次，命中当天 → 调用 notify 工具
  └── last_notified_date 防重复触发
```

### intent 字段结构

```json
// once timer（自动派生）
{ "type": "once" }

// recurring timer
{ "type": "recurring", "human": "工作日早9点" }

// 节日（内置表）
{ "type": "holiday", "name": "中秋节", "advance_days": 1, "time": "09:00" }

// 用户农历日期
{ "type": "lunar_date", "lunar_month": 3, "lunar_day": 8, "advance_days": 1, "time": "09:00" }
```

### 数据文件

- `implementation/runtime/data/timers.json` — 现有，新增 `intent` 字段持久化
- `implementation/runtime/data/calendar_reminders.json` — 新建，CalendarChecker 管理

### 内置节日表

仅农历节日（公历节日用 cron 表达即可）：
- 春节（农历1/1）、元宵（1/15）、端午（5/5）、七夕（7/7）
- 中秋（8/15）、重阳（9/9）、腊八（12/8）

### lunardate 库选型

选用 `lunardate`（PyPI）：
- 纯 Python 实现，无 C 扩展依赖
- 覆盖 1900–2100 年
- API 简洁：`LunarDate.today()` / `LunarDate(year, month, day).to_solar_date()`
- 维护活跃，MIT 协议

### 向后兼容

`intent` 字段可选，旧数据无 intent 时按 type 自动派生：
- `type="cron"` → `intent={"type":"recurring"}`
- `type="once"` → `intent={"type":"once"}`

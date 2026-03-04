# HEARTBEAT.md - 定期巡检

> 希露菲的定期检查清单。由 heartbeat.sh 自动执行，发现异常通过 Telegram 通知用户。

## 1. 服务健康

```bash
cd /Users/kaiqidong/Devkit && ./check.sh --json
```

检查 `services` 字段：
- SearXNG、STT 代理、Gateway 任一挂掉 → 尝试重启 (`./start.sh`)，仍失败则通知用户
- OpenCami 挂掉 → 通知用户

## 2. Cursor 任务状态

```bash
pgrep -f "cursor agent"
```

- 有 Cursor Agent 在跑且超过 30 分钟 → 通知用户当前状态
- 无任务运行且有待办事项 → 可选提醒

## 3. 新邮件

```bash
himalaya envelope list --page-size 5
```

- 有未读邮件 → 摘要推送（发件人 + 主题）
- 过滤掉广告/通知类邮件，只推送重要的

## 4. 项目进度

检查 `STATUS.md` 最后更新时间：

```bash
stat -f %m /Users/kaiqidong/Devkit/STATUS.md
```

- 超过 48 小时未更新且有"进行中"项 → 提醒用户

## 5. Git 状态

```bash
cd /Users/kaiqidong/Devkit && git status --short | wc -l
```

- 未提交变更超过 20 个文件 → 提醒用户提交或清理

## 6. 待确认项

```bash
grep -c '待确认' /Users/kaiqidong/Devkit/STATUS.md
grep -c '待确认' /Users/kaiqidong/Devkit/DECISIONS.md
```

- 有积压的待确认项 → 提醒用户决策

## 7. 日程提醒（依赖 CalDAV 配置后启用）

```bash
khal list today tomorrow
```

- 今天/明天有日程 → 每天早晨摘要推送

## 通知规则

- **紧急**（服务挂掉、构建失败）：立即推送
- **重要**（新邮件、待确认项）：汇总后每 30 分钟最多推一次
- **日常**（日程、进度提醒）：每天早/晚各一次
- **静默时间**：23:00-08:00 不推送（紧急除外）

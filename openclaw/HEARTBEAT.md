# HEARTBEAT.md - 定期检查

## 1. Cursor 任务状态

检查是否有正在运行的 `cursor` 进程：
```bash
pgrep -f "cursor agent" && echo "有 Cursor 任务在跑"
```
如果运行超过 30 分钟，通知用户当前状态。

## 2. 项目进度

检查 `/Users/kaiqidong/workspace/Devkit/STATUS.md` 最后更新时间。
如果超过 24 小时且有未完成任务，提醒用户。

## 3. 待确认项

检查 `/Users/kaiqidong/workspace/Devkit/DECISIONS.md` 中是否有标记为「待确认」的条目。
如有，提醒用户。

## 4. Git 状态

检查项目仓库是否有未提交的变更：
```bash
cd /Users/kaiqidong/workspace/Devkit && git status --short
```
如果有大量未提交变更，考虑提交或提醒用户。

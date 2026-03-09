# HEARTBEAT.md - 巡检指引

定期巡检时，重点关注：

1. 关键服务是否存活（风铃、STT、Timer API、SearXNG）
2. `implementation/STATUS.md` 是否长期未更新但仍有进行中事项
3. Git 工作区是否积累过多未提交改动
4. 是否有需要主动通知用户的重要异常

## 常用检查

```bash
./check.sh
stat -f %m implementation/STATUS.md
```

设计决策参考：`design/decisions/README.md`

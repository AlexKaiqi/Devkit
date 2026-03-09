# Session Identity 与跨渠道连续性

本文档描述目标态设计中，`session_key` 如何在渠道间共享、任务状态如何持久化，以及如何实现跨渠道结果投递。

## 问题背景

系统同时支持风铃（桌面）和 Telegram（移动）两个入口，但任务属于用户而不是某个会话窗口。要实现"桌面发起、移动端收到结果"，需要解决三个子问题：

1. **身份统一**：两个渠道的用户是同一个人，系统必须有统一身份映射
2. **任务归属**：任务必须归属于用户身份，而不是某个渠道会话
3. **结果投递**：任务完成时，系统知道把结果送向哪个渠道

## 设计决策

### session_key 命名约定

每个渠道会话分配一个 `session_key`，格式为：

```
{channel}-{user_id}-{session_suffix}
```

例如：
- `fengling-local-20260309` — 风铃桌面会话（单用户，以日期区分）
- `tg-123456789` — Telegram 用户 ID `123456789`

`session_key` 由渠道层在会话建立时分配，runtime 只消费它，不生成它。

### 用户身份映射

V1 采用本地配置文件 `implementation/assets/persona/USER.md` + 环境变量的方式绑定身份：

- 风铃：单用户，`session_key` 固定前缀 `fengling-local`
- Telegram：`TELEGRAM_USER_ID` 环境变量定义允许的用户 ID

多渠道身份映射表（V1 最小实现）：

```yaml
# implementation/data/identity-map.yml
user_id: "local"
channels:
  fengling:
    session_prefix: "fengling-local"
  telegram:
    user_id: "${TELEGRAM_USER_ID}"
    session_prefix: "tg-${TELEGRAM_USER_ID}"
notify_preference:
  async_results: "telegram"   # 异步结果优先投递到哪个渠道
  reminders: "telegram"
```

### 任务注册表

V1 使用本地 JSONL 文件作为任务注册表，避免引入数据库：

```
implementation/data/tasks.jsonl
```

每行一条任务记录：

```json
{
  "task_id": "task-20260309-001",
  "session_key": "fengling-local-20260309",
  "source_channel": "fengling",
  "title": "翻译论文",
  "state": "waiting_external",
  "created_at": "2026-03-09T10:00:00Z",
  "updated_at": "2026-03-09T10:00:05Z",
  "artifacts": [],
  "continuation_of": null,
  "next_action": "wait_for_translation_result"
}
```

任务状态更新以追加新行的方式写入，以最后一条相同 `task_id` 的记录为准（append-only，可回溯）。

### 跨渠道结果投递

任务完成时，runtime 根据 `identity-map.yml` 中的 `notify_preference` 决定向哪个渠道推送结果：

```
任务完成
  └─ ResultComposer 生成回报内容
      └─ 查询 notify_preference
          ├─ 当前渠道（发起渠道）：直接回复
          └─ 异步结果偏好渠道（如 Telegram）：通过 EventSystem 发布 channel.deliver 事件
```

`channel.deliver` 事件 payload：

```json
{
  "session_key": "tg-123456789",
  "task_id": "task-20260309-001",
  "content": "论文翻译完成，共 12 页。",
  "attachments": ["paper_cn.md"]
}
```

### 任务跨渠道追溯

Telegram 收到结果通知时，通知中携带 `task_id`，用户可在风铃中用该 ID 查看完整执行记录：

- Telegram 通知格式：`✓ [任务名称] 已完成 (task-id: xxx)\n摘要...`
- 风铃侧：支持按 `task_id` 从 `tasks.jsonl` 检索任务详情

## 接口约定

### IdentityResolver（runtime 内部）

```python
def get_notify_channels(task_id: str) -> list[str]:
    """返回该任务结果应投递的渠道 session_key 列表"""

def resolve_session_key(channel: str, raw_id: str) -> str:
    """将渠道原始会话标识转换为统一 session_key"""
```

### 任务注册表读写

```python
def append_task(task: TaskRecord) -> None:
    """追加任务记录到 tasks.jsonl"""

def get_task(task_id: str) -> TaskRecord | None:
    """按 task_id 取最新状态"""

def list_tasks(state: str | None = None) -> list[TaskRecord]:
    """列出任务，可按状态过滤"""
```

## V1 约束

- 单用户场景；多用户支持保留扩展点但不在 V1 实现
- 任务注册表用 JSONL 文件，不引入数据库
- `identity-map.yml` 手工配置，不自动注册新渠道

## 相关文档

- [event-system.md](../interfaces/event-system.md)
- [runtime-core.md](runtime-core.md)
- [任务生命周期与续作](../../requirements/core/task-lifecycle.md)
- [cross-channel-delivery-001](../../requirements/acceptance/channels/cross-channel-delivery-001.json)

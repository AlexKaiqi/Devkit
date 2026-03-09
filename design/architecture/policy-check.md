# Policy Check 设计

Policy Check 是 runtime 在工具真正执行前的最后一道强制检查。它确保委托边界不只作为 prompt 前提存在，而是在执行层面有硬约束。

## 设计定位

模型可以"提出要做什么"，但不能拥有最终执行权。Policy Check 是两者之间的强制关卡：

```
模型输出 tool_call
  └─ Policy Check（runtime 层）
      ├─ PASS → 执行工具
      └─ BLOCK → 拒绝执行 / 转 needs_confirmation
```

## 委托边界数据格式

委托边界分为两部分：静态边界（长期稳定）和动态边界（任务/会话级临时授权）。

### 静态边界（`implementation/assets/persona/POLICY.md`）

用 Markdown 定义，人类可读，Agent 可解析：

```markdown
# 委托边界

## 永不默认执行

- 向任何外部联系人发送消息（需每次确认）
- git push / git commit（需每次确认）
- 删除文件（需每次确认）
- 任何涉及支付或账户的操作

## 可自动执行（L0/L1）

- 读取 ~/projects/ 下任意文件
- 在 /tmp/ 或项目目录内创建临时文件
- 执行只读 shell 命令（ls, find, grep, cat 等）
- 搜索、总结、翻译

## 需要确认（L2）

- 写入 ~/projects/ 下已有文件
- 发送 Telegram 消息
- 调用任何外部 API 写入端点
```

### 动态边界（运行时 in-memory，绑定 task_id）

```python
@dataclass
class DynamicGrant:
    task_id: str
    action: str          # 被授权的动作，如 "git_commit"
    scope: str           # 作用范围，如 "~/projects/devkit"
    expires_at: float    # Unix timestamp，任务结束或超时后失效
    granted_at: float
```

动态授权在用户确认后由 Task Orchestrator 写入，Policy Check 执行前查询。

## PolicyCheck 接口

```python
@dataclass
class PolicyDecision:
    allowed: bool
    reason: str
    action_required: str | None   # "confirm" | "clarify" | None


def check(
    tool_name: str,
    tool_args: dict,
    task_id: str | None,
    risk_level: str,              # L0 / L1 / L2 / L3
) -> PolicyDecision:
    """
    在工具执行前调用。
    - L0/L1：检查静态边界白名单，通常 PASS
    - L2：查动态边界，无授权则返回 action_required="confirm"
    - L3：始终返回 action_required="confirm"（每次必确认）
    """
```

## 风险级别判断

工具调用的风险级别由工具定义时声明，不由模型自由判断：

```python
# 工具定义示例
TOOL_RISK_MAP = {
    "read_file":       "L0",
    "search":          "L0",
    "write_file":      "L1",
    "run_shell":       "L1",   # 只读命令；写入/删除命令自动升级到 L2
    "git_commit":      "L2",
    "git_push":        "L2",
    "send_message":    "L2",
    "delete_file":     "L2",
    "send_email":      "L2",
    "payment":         "L3",
}
```

`run_shell` 等泛化工具需在 Policy Check 内对参数做二次判断（如命令包含 `rm -rf` 则升级到 L2/L3）。

## 检查流程

```
1. Tool Coordinator 收到 model tool_call
2. 解析 tool_name 和 tool_args
3. 查 TOOL_RISK_MAP 确定 risk_level
4. 调用 PolicyCheck.check(tool_name, tool_args, task_id, risk_level)
5a. PASS → 执行工具，记录 audit log
5b. BLOCK (action_required="confirm") → 任务转 needs_confirmation，向用户展示确认请求
5c. BLOCK (action_required="clarify") → 任务转 needs_clarification，向用户澄清范围
```

## 审计记录

每次 Policy Check 必须写入审计日志，字段：

```json
{
  "ts": "2026-03-09T10:05:00Z",
  "task_id": "task-20260309-001",
  "tool": "send_message",
  "args_summary": "to=张伟, channel=telegram",
  "risk_level": "L2",
  "decision": "blocked",
  "action_required": "confirm",
  "dynamic_grant": null
}
```

确认后执行时，追加一条 `decision=allowed, dynamic_grant=<grant_id>` 的记录。

## 相关文档

- [runtime-core.md](runtime-core.md)
- [信任模型与委托边界需求](../../requirements/core/trust-boundaries.md)
- [trust-boundary-001](../../requirements/acceptance/core/trust-boundary-001.json)
- [trust-boundary-002](../../requirements/acceptance/core/trust-boundary-002.json)

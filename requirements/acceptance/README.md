# 验收用例

`requirements/acceptance/` 用来定义“实现之前就应该存在”的验收场景。

这里的内容属于需求，而不是实现测试代码。它回答的是：

- 要验证什么用户承诺
- 哪些行为必须发生
- 哪些行为绝对不能发生
- 最终怎样才算通过

## 边界

- 可以写：场景、输入、上下文、期望行为、禁止行为、通过标准、所需证据。
- 不写：端口、类名、脚本命令、测试框架、具体 runner 实现。

## 目录建议

| 目录 | 说明 |
|------|------|
| `core/` | 通用能力的验收场景 |
| `channels/` | 风铃主体验与外部集成体验验收 |
| `domains/` | 开发、科研、人际等专业能力验收 |
| `regressions/` | 从真实失败案例沉淀出的回归样本 |

## 一个验收用例应包含

- `id`：稳定标识
- `title`：场景名称
- `capability`：对应能力
- `scenario`：用户场景描述
- `input`：用户输入
- `context`：前置条件
- `expected.must`：必须满足的行为
- `expected.must_not`：绝不能发生的行为
- `evidence.required`：判断是否通过时需要的证据
- `evaluation`：建议的评测方式，例如 deterministic / llm / hybrid

## 原则

1. 先写验收用例，再写实现。
2. 验收用例优先围绕用户任务，而不是围绕内部模块。
3. 回归样本优先来自真实失败，而不是想象中的边角场景。
4. 只有当一个能力拥有验收场景时，它才算真正进入产品边界。

## 已有用例

### core/

| 文件 | 能力 | 场景摘要 |
|------|------|----------|
| [task-continuation-001.json](core/task-continuation-001.json) | task-lifecycle | 等待后的任务应以续作任务继续 |
| [task-state-reporting-001.json](core/task-state-reporting-001.json) | task-lifecycle | 长任务应立即确认并进入可追踪状态 |
| [trust-boundary-001.json](core/trust-boundary-001.json) | trust-boundaries | 破坏性写入前必须确认 |
| [trust-boundary-002.json](core/trust-boundary-002.json) | trust-boundaries | L2 外发动作（发送消息）必须在执行前确认 |
| [memory-recall-001.json](core/memory-recall-001.json) | memory-knowledge | 后续任务能复用先前积累的长期记忆 |
| [memory-correction-001.json](core/memory-correction-001.json) | memory-knowledge | 用户纠正错误记忆后系统应更新并不再重犯 |

### channels/

| 文件 | 能力 | 场景摘要 |
|------|------|----------|
| [fengling-response-mode-001.json](channels/fengling-response-mode-001.json) | fengling-channel | 风铃应区分对话文本与附件 |
| [cross-channel-delivery-001.json](channels/cross-channel-delivery-001.json) | external-delivery | 若启用 Telegram 集成，风铃发起的异步任务结果应能送达 Telegram |

## 参考

- [case-template.json](case-template.json)

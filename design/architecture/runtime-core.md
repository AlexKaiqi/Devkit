# Runtime Core

Runtime Core 是共享分身能力的核心承载层。

## 职责

- 接收渠道请求并组装执行上下文。
- 把用户意图映射为任务对象。
- 在执行前执行委托边界检查。
- 调用工具协议并协调多轮执行。
- 管理记忆层与知识层读写。
- 触发事件、续作和主动回报。

## 内部子模块

| 模块 | 职责 |
|------|------|
| Session Manager | 管理渠道会话与共享身份映射 |
| Context Assembly | 拼装系统指令、任务状态、记忆、附件与最近上下文 |
| Task Orchestrator | 任务状态流转、子任务推进与续作 |
| Policy Check | 委托边界、确认策略与执行前检查 |
| Tool Coordinator | 多轮工具调用与结果聚合 |
| Memory Gateway | 记忆层写入、检索、纠错与归档 |
| Knowledge Gateway | 知识层查询、提炼、引用与来源追踪 |
| Result Composer | 输出对话文本、附件和进度回报 |

## Context Assembly 策略

Context Assembly 负责将多来源信息组装成送入模型的最终上下文。组装质量直接影响模型输出效果。

### 组装顺序与优先级

上下文按以下顺序拼装，越靠前的部分越重要，越靠后越容易被截断：

1. **System Prompt 核心**：人格（SOUL.md、IDENTITY.md）+ 全局行为约定
2. **委托边界摘要**：当前会话的风险策略和已授权/禁止动作列表
3. **长期记忆摘要**：从 MEMORY.md 提取的用户偏好、约束和关键背景（≤ 500 tokens）
4. **相关知识**：按当前任务 tags 从 Knowledge Gateway 召回的知识条目（≤ 800 tokens）
5. **任务状态上下文**：当前任务 ID、状态、已产出的产物摘要（如有）
6. **最近会话历史**：最近 N 轮对话（根据剩余 token 预算动态裁剪，最少保留最近 3 轮）
7. **当前用户输入**：含附件引用

### Token 预算分配（参考值）

| 部分 | 预算上限 | 裁剪策略 |
|------|---------|----------|
| System Prompt 核心 | 1 000 | 不裁剪 |
| 委托边界摘要 | 300 | 不裁剪 |
| 长期记忆摘要 | 500 | 超出时只保留最近更新的条目 |
| 相关知识 | 800 | 按相关性得分截取 top-K |
| 任务状态上下文 | 400 | 不裁剪 |
| 会话历史 | 剩余预算 | 从最旧轮次开始截断，保留最近 ≥ 3 轮 |
| 当前用户输入 | 不限 | 不裁剪 |

### 续作任务的上下文组装

续作任务不重放旧对话历史，而是替换为：

- 旧任务的 `title` + `intent`
- 最后已知状态和卡点描述
- 已产出产物的文件摘要
- 相关的审计日志关键事件（不超过 300 tokens）

## 设计原则

1. runtime 持有产品资产，模型只提供推理能力。
2. 任务必须独立于聊天气泡存在，能够被续作。
3. 记忆与知识是长期资产，不能只依赖上下文窗口。
4. 所有高风险执行都必须经过最后一步边界检查。
5. 长时间等待通过事件系统承载，不占用主对话。

## 相关文档

- [system-overview.md](system-overview.md)
- [knowledge-gateway.md](knowledge-gateway.md)
- [session-identity.md](session-identity.md)
- [policy-check.md](policy-check.md)
- [event-system.md](../interfaces/event-system.md)

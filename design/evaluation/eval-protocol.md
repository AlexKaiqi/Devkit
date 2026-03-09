# 评测协议

## 目标

把“先定义验收，再让 AI 实现，再用证据评估”的流程稳定下来。

## 基本流程

1. 在 `requirements/acceptance/` 定义场景。
2. 在 `design/evaluation/` 定义评测方式、rubric 和 evidence schema。
3. 在 `implementation/` 执行场景，生成 evidence trace。
4. 先跑 deterministic checks。
5. 对剩余语义判断部分再运行 LLM judge。
6. 输出统一 report，并把失败样本沉淀成 regression case。

## Candidate 与 Judge 分离

评测时应逻辑上分离两类角色：

- `candidate`：被评估的实现或 Agent 输出
- `judge`：负责根据 evidence 和 rubric 做判断

理想情况下，两者不应共享同一个“默认相信自己”的上下文。

## Judge 输入

LLM judge 不应只看最终一句回复。最小输入应包含：

- 用户输入
- 前置上下文摘要
- 关键 tool trace
- 关键任务状态
- 最终回复
- 附件或产物摘要

如果没有 evidence，只看最终回复，评测结果会高度不稳定。

## 推荐评测顺序

### 第一步：硬约束

先检查：

- 必须字段是否存在
- 危险动作是否越界
- 是否创建了预期对象
- 是否产生了必要附件
- 是否记录了必要 trace

### 第二步：语义判断

再评：

- 是否抓住用户真正意图
- 是否说明了关键风险
- 是否正确利用已有上下文
- 是否形成了对用户可用的产物

## 结果模型

一个 case 的最终结果建议拆成三部分：

- `deterministic_result`
- `llm_judge_result`
- `final_decision`

其中 `final_decision` 不能绕过 deterministic failures。

## 稳定性原则

1. 高价值场景支持多次运行，记录通过率。
2. Judge 必须绑定 rubric 名称和版本。
3. Report 中保留 evidence 引用，允许人工复查。
4. 回归场景优先来自真实失败，而不是虚构场景。

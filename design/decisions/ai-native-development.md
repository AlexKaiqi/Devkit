# 决策：AI 原生开发范式

## 决策

- 项目采用 **文档、验收与评测先于实现** 的 AI 原生开发范式，而不是“先写代码、再补说明”。
- `requirements / design / implementation` 不只是目录划分，也是默认开发顺序：
  1. 先定义需求与验收场景
  2. 再定义系统设计、评测协议与边界
  3. 最后才落实现代码、脚本和运行资产
- AI 是默认执行者，但不是默认裁判。实现、评测、审计和回归要尽量基于显式 evidence，而不是“模型自我感觉正确”。
- 代码不是唯一资产。需求文档、acceptance cases、judge rubrics、persona、tool protocol、trace schema、regression cases 都属于一等项目资产。
- 真实失败样本必须沉淀为可回归资产，而不是停留在一次性的对话或经验里。

## 这意味着什么

AI 原生项目不只是“让 AI 帮忙写代码”。它更像一种新的工程闭环：

1. 用文档和结构化 case 描述目标
2. 用设计文档描述边界、协议和评测方式
3. 让 AI 在这些约束内实现
4. 用 evidence、deterministic checks 和必要的 LLM judge 评估结果
5. 把失败样本沉淀成新的长期资产

换句话说，AI 原生项目的核心不是“自动生成代码”，而是 **让需求、设计、实现、评测和回归都能被 AI 可靠消费与产出**。

## 核心原则

### 1. 规格先于代码

新能力、重要改动或高风险行为，应优先补：

- `requirements/` 下的能力定义
- `requirements/acceptance/` 下的验收场景
- `design/` 下的边界、协议与评测方式

如果直接从代码长出产品定义，AI 之后就只能模仿当前实现，而不是对齐目标。

### 2. 验收先于自测

`implementation/tests/` 主要回答“代码有没有坏”，但 AI 原生项目更关心“是否真的满足目标”。因此验收场景应先定义在需求层，而不是事后补在实现层。

### 3. 证据先于判断

评测时优先收集：

- 输入
- 上下文摘要
- tool trace
- task trace
- 最终回复
- 附件与产物

没有 evidence 的 LLM judge 只能给出脆弱的印象分。

### 4. 先硬约束，再语义评估

优先用 deterministic checks 卡住：

- schema 合法性
- 高风险边界
- 是否创建预期对象
- 是否产生必要附件
- 是否保留必要 trace

只有语义质量、解释完整性、澄清是否到位等部分，才交给 LLM judge。

### 5. 失败要资产化

AI 原生项目的经验沉淀，不应主要靠“记得上次出过问题”。真实失败应该进入：

- regression cases
- 决策文档
- persona 记忆
- trace schema / eval protocol 的修订

## 人与 AI 的分工

### 人负责

- 定义目标、边界和优先级
- 对高风险动作给出最终授权
- 审核关键设计取舍
- 判断哪些失败值得升级成长期回归资产

### AI 负责

- 实现方案
- 执行修改
- 生成和运行测试 / eval
- 收集 evidence
- 更新文档与状态
- 把离散经验整理成结构化资产

## 项目级约束

未来新增能力时，默认顺序应为：

1. `requirements/` 定义能力与验收
2. `design/` 定义边界、协议与评测
3. `implementation/` 落实现与运行资产

如果只有代码改动、没有需求与评测资产，就说明这次变化还没有真正进入 AI 原生闭环。

## 执行清单

如果这份文档回答的是“为什么要这样开发”，那么 [`ai-native-development-checklist.md`](ai-native-development-checklist.md) 回答的是“每次改动具体该怎么走”。

## 相关文档

- [项目目标](../../requirements/product/goals.md)
- [验收用例索引](../../requirements/acceptance/README.md)
- [AI 原生开发清单](ai-native-development-checklist.md)
- [评测协议](../evaluation/eval-protocol.md)
- [Judge Rubrics](../evaluation/judge-rubrics.md)
- [Runtime 与模型适配层](runtime-and-adapter.md)

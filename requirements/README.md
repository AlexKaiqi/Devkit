# Requirements

`requirements/` 只描述产品需要什么，不描述当前怎么实现。

## 边界

- 可以写：用户、场景、对象、流程、规则、验收标准、指标。
- 不写：端口、类名、脚本命令、供应商 SDK、目录实现细节。

## 目录

| 目录 | 说明 |
|------|------|
| [product/](product/) | 产品定位、目标、衡量方式 |
| [core/](core/) | 任务、信任、记忆与知识等通用需求 |
| [channels/](channels/) | 风铃等入口的交互需求 |
| [domains/](domains/) | 开发、科研、人际等专业能力需求 |
| [capabilities/](capabilities/) | 能力需求总览 |
| [acceptance/](acceptance/) | 实现前定义的验收场景与回归样本 |

## 核心文档

- [产品总览](product/overview.md)
- [项目目标](product/goals.md)
- [产品指标](product/metrics.md)
- [任务生命周期与续作](core/task-lifecycle.md)
- [信任模型与委托边界](core/trust-boundaries.md)
- [记忆层与知识层](core/memory-knowledge.md)
- [能力需求总览](capabilities/overview.md)
- [验收用例索引](acceptance/README.md)

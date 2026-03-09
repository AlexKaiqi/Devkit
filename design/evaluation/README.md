# Evaluation Design

`design/evaluation/` 描述 AI 原生开发中的测试与评测机制。

这里不定义用户需求本身，也不写具体 pytest 或 runner 代码。它回答的是：

- 哪些场景适合 deterministic 检查
- 哪些场景需要 LLM judge
- judge 应该看哪些证据
- 评测结果怎样形成稳定、可回归的报告

## 核心文档

- [测试分型](test-taxonomy.md)
- [评测协议](eval-protocol.md)
- [Judge Rubric](judge-rubrics.md)
- [Evidence Trace Schema](trace-schema.md)

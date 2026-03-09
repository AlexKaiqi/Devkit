# AI 原生开发清单

这份清单不是新的原则文档，而是 [`ai-native-development.md`](ai-native-development.md) 的执行版。

默认情况下，新增能力、重要改动、高风险行为调整、跨渠道体验修改，都应从上到下过一遍。只有能明确说明“为什么这一步不需要”时，才跳过。

## 0. 先判断这次改动属于什么

- [ ] 是新增能力、行为变更、缺陷修复、纯重构、文档修订，还是评测资产补齐。
- [ ] 这次改动是否改变用户承诺、交互行为、风险边界或产物形态。
- [ ] 这次改动是否涉及高风险操作、任务续作、记忆/知识、异步执行或多入口一致性。

## 1. 先补需求层

如果改动影响用户可感知行为，先看 `requirements/`，而不是先改代码。

- [ ] 必要时更新 `requirements/product/overview.md`、`requirements/product/goals.md` 或相关能力文档。
- [ ] 在 `requirements/acceptance/` 新增或更新验收场景。
- [ ] 明确 `expected.must`、`expected.must_not`、`evidence.required`、`evaluation`。
- [ ] 确认验收场景描述的是用户任务，不是内部实现细节。

## 2. 再补设计层

当边界、协议、对象模型、评测方式发生变化时，补设计而不是把这些信息塞进实现注释里。

- [ ] 必要时更新 `design/architecture/`、`design/interfaces/` 或 `design/decisions/`。
- [ ] 确认这次变化属于 deterministic、llm 还是 hybrid evaluation。
- [ ] 如果 judge 规则变了，更新 `design/evaluation/judge-rubrics.md`。
- [ ] 如果 evidence 结构变了，更新 `design/evaluation/trace-schema.md`。
- [ ] 如果评测流程变了，更新 `design/evaluation/eval-protocol.md`。

## 3. 最后改实现层

只有在需求和设计已经足够清楚后，才进入 `implementation/`。

- [ ] 修改源码、脚本、配置、persona、tests 或 eval runner。
- [ ] Python 命令统一使用项目内 `.venv/`。
- [ ] 对照验收场景实现需要被观察到的行为，而不是只让单元测试通过。
- [ ] 如果改动引入新的运行资产或入口，补实现层导航文档。

## 4. 做验证，而不是只做自测

`implementation/tests/` 和 `implementation/evals/` 解决的问题不同，两者不要互相替代。

- [ ] 运行必要的 deterministic tests，确认代码没有明显回归。
- [ ] 行为变化时，运行对应 acceptance/eval 流程。
- [ ] 收集足够 evidence：输入、上下文摘要、tool trace、task trace、最终回复、附件/产物。
- [ ] 先检查 schema、边界、附件、trace 等硬约束，再做语义评分。
- [ ] 如果使用 LLM judge，确保 judge 基于 evidence，而不是裸看最终回复。

## 5. 把失败沉淀成资产

AI 原生项目的关键不是“修过一次”，而是“以后不会再无声地重复犯错”。

- [ ] 如果发现真实失败，优先补成 `requirements/acceptance/regressions/` 或其他回归资产。
- [ ] 如果失败暴露了设计问题，更新相关决策文档。
- [ ] 如果失败暴露了评测盲区，更新 rubric、protocol 或 trace schema。
- [ ] 如果失败暴露了长期协作经验，考虑写入 persona 记忆。

## 6. 收尾

- [ ] 更新索引文档，让后来者能找到新增资产。
- [ ] 更新 `implementation/STATUS.md`，记录这次沉淀了什么。
- [ ] 标出仍待确认的问题，不要把不确定性伪装成完成。

## 哪些情况可以简化

- 纯文案、错别字、死链接修复：通常不需要新增 acceptance case，但仍应更新相关索引。
- 纯内部重构且不改变外部行为：通常不需要改 `requirements/`，但应保留必要 tests。
- 高风险边界、任务续作、跨入口体验、记忆/知识行为：默认不能跳过 acceptance 和 evidence 设计。

## 默认顺序

1. 判断改动类型与风险
2. 先补 `requirements/`
3. 再补 `design/`
4. 最后改 `implementation/`
5. 运行 tests 与 eval
6. 把失败和经验沉淀为长期资产
7. 更新索引与 `implementation/STATUS.md`

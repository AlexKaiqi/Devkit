# 设计决策：方法论本体强制执行

**状态**: 已通过
**日期**: 2026-03-17
**作者**: AI-native development workflow

## 问题

Devkit 的 AI 原生开发方法论是纯文本约定（`design/decisions/ai-native-development.md`），AI agent 在实际执行中可选择性忽略，导致频繁跳过"先写验收场景再写代码"等关键步骤。

## 决策

将方法论提升为**可查询、可验证、可拦截的结构化约束系统**，包含四个组件：

1. **YAML 本体**（`design/ontology/methodology.yaml`）：声明 ChangeType、Phase、GateType 三个类及实例，以及每种 ChangeType 的强制阶段路径和门控规则。
2. **门控检查器**（`implementation/runtime/methodology/gate_checker.py`）：对每个门控执行文件系统扫描或命令执行，返回结构化 `GateResult`。
3. **Feature 状态机**（`implementation/runtime/methodology/engine.py`）：管理 Feature 的生命周期，在 `advance_phase` 时强制执行所有门控检查。
4. **Agent 拦截器**（`implementation/runtime/methodology/interceptor.py`）：在 tool call 执行前检查方法论状态，对未满足门控的写操作返回 hard block。

## 关键设计选择

### 为什么用 YAML 本体而不是 Python 枚举/硬编码？

- YAML 可被非程序员读懂和修改，满足"方法论本身也是可演化的文档"原则
- YAML 本体可被 AI agent 直接读取和解释，增强自解释性
- 与 `design/` 层的其他 YAML 保持一致的格式约定

### 为什么 Feature 和 Task 分离？

- Task 是执行层概念（"当前在做什么"），Feature 是方法论层概念（"这个变更属于哪种类型"）
- 一个 Feature 可以跨越多个 Task（例如 requirements Task + implementation Task）
- 两者解耦允许方法论引擎在 Task 图不可用时独立工作

### 为什么 hard block 而不是只记录警告？

- 软警告在 AI agent 上下文中效果不佳，agent 倾向于继续执行
- hard block 在 tool call 层面强制执行，不依赖 agent 的"理解"
- 提供 `METHODOLOGY_ENFORCEMENT=off` 环境变量作为紧急逃生阀

### Neo4j 可用性降级

- Feature 状态机在 Neo4j 不可用时降级为内存字典模式
- 降级模式支持完整的门控检查功能，仅丢失跨会话持久化
- 与 Task Graph 使用相同的降级模式设计原则

### 文件系统作为真相来源

- 对 `acceptance_case_exists`、`design_decision_exists` 等检查，使用文件系统扫描而非 Neo4j 查询
- 原因：验收场景文件（JSON）和设计决策文件（MD）本身就是 `requirements/` 和 `design/` 层的主要产物
- 文件系统检查不依赖 Neo4j 连接，提高可靠性

## 影响范围

- **新增**: `design/ontology/` 目录（本体定义）
- **新增**: `implementation/runtime/methodology/` 包（完整实现）
- **新增**: `implementation/runtime/tools/skills/methodology/` 包（Agent skill）
- **修改**: `implementation/runtime/agent.py`（上下文注入 + 拦截器集成）
- **修改**: `implementation/runtime/task_graph/graph_store.py`（Feature 索引）
- **修改**: `implementation/channels/fengling/server.py`（startup 初始化）
- **修改**: `implementation/channels/fengling/static/ops.html`（方法论面板）

## 验收

见 `requirements/methodology/enforcement.md` 的验收标准 AC-1 至 AC-7。

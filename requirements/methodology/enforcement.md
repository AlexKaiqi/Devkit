# 方法论强制执行需求

## 问题陈述

Devkit 有完善的 AI 原生开发方法论文档（`design/decisions/ai-native-development.md`），但 AI agent 在实际执行中经常跳过关键步骤：
- 跳过"先写验收场景再写代码"
- 跳过"先有设计决策再写代码"
- 跳过"重构后必须验证现有测试通过"

根因：方法论是纯文本约定，AI 可选择性忽略。文本约定对 AI agent 缺乏强制力。

## 目标

将方法论从文本约定提升为**可查询、可验证、可拦截的结构化约束**：

1. **本体化**：将 ChangeType / Phase / Gate 定义为结构化 YAML，可被程序查询
2. **门控化**：在关键阶段转换点设置文件系统或运行时检查，自动判断是否满足条件
3. **拦截化**：当 AI 试图调用写入类工具（write_file, exec, code_agent）时，若方法论门控未通过则返回阻塞信号
4. **可视化**：在 ops.html 面板展示活跃 Feature 的方法论状态

## 验收标准

### AC-1: 本体查询
- 给定 `change_type=new_capability`，能查询出完整的 phases 列表
- 给定 `change_type=new_capability, phase_from=requirements, phase_to=design`，能查询出对应的门控规则

### AC-2: 门控检查
- 当 `requirements/acceptance/` 下不存在含 feature_slug 的 JSON 文件时，`acceptance_case_exists` 检查返回 `passed=False`
- 当文件存在时返回 `passed=True`
- 当 `existing_tests_pass` 对应命令退出码为 0 时返回 `passed=True`

### AC-3: CLI 工具
```bash
.venv/bin/python -m implementation.runtime.methodology.cli check \
  --feature reminder-v2 --change-type new_capability
```
- 输出包含每个阶段的状态（✅ / ⛔ / ⏸）
- hard_block 未通过时输出清晰的阻塞原因

### AC-4: Feature 生命周期（需 Neo4j）
- `create_feature(title, change_type)` 创建 Feature 节点并存入 Neo4j
- `advance_phase(feature_id)` 在门控全通过时将 Feature 推进到下一阶段，否则返回失败的门控列表
- `skip_phase(feature_id, phase, reason)` 记录跳过理由

### AC-5: Agent 上下文注入
- Agent 每轮调用时，若当前 session 有活跃 Feature，将门控状态注入 system prompt
- 注入格式清晰标明 Feature 名称、当前阶段、未通过的门控

### AC-6: 拦截器
- 当 Feature 在 `requirements` 或 `design` 阶段，且 `acceptance_case_exists` 未通过时
- Agent 调用 `write_file` 工具被拦截，返回 `⛔ 方法论门控未通过: 新能力必须先有验收场景`
- 设置环境变量 `METHODOLOGY_ENFORCEMENT=off` 可关闭拦截

### AC-7: ops 面板
- `GET /api/methodology/features` 返回活跃 Feature 列表及门控状态
- ops.html 中"方法论"面板显示 Feature 列表、当前阶段、门控状态（✅/⛔）

## 优先级

- P0: AC-1, AC-2, AC-3（Phase 1 — 无外部依赖，立即可用）
- P1: AC-4（Phase 2 — 需要 Neo4j）
- P1: AC-5, AC-6（Phase 3 — Agent 集成）
- P2: AC-7（Phase 4 — 可视化）

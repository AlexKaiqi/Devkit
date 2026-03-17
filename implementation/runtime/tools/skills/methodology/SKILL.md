---
name: methodology
always: false
keywords: [方法论, methodology, feature, 验收场景, acceptance, 设计决策, design decision, gate, 门控, 阶段, phase, 变更类型, change type, 强制, enforcement, 创建功能, create feature, 检查门控, check gates, 推进阶段, advance phase, 关联产物, link artifact]
---
# Methodology Skill

方法论本体强制执行能力。管理 Feature 生命周期，强制 AI 原生开发方法论。

## 工具列表

- `create_feature` — 创建一个新 Feature，指定标题和 ChangeType
- `check_gates` — 检查指定 Feature 当前阶段的门控状态
- `advance_phase` — 尝试将 Feature 推进到下一阶段（门控未通过时返回阻塞原因）
- `link_artifact` — 将验收场景或设计决策文件关联到 Feature

## 使用场景

当用户要开始一个新功能开发、行为变更或重构时：
1. 先用 `create_feature` 创建 Feature，明确 ChangeType
2. 按方法论完成各阶段产物（验收场景、设计决策）
3. 用 `check_gates` 确认门控状态
4. 用 `advance_phase` 推进阶段

## ChangeType 速查

| 类型 | 说明 |
|------|------|
| `new_capability` | 全新功能 |
| `behavior_change` | 已有功能行为变更 |
| `bug_fix` | 修复 bug |
| `refactoring` | 内部重构（不改外部行为） |
| `doc_revision` | 文档修改 |
| `eval_asset` | 评测资产 |

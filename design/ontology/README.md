# 方法论本体（Methodology Ontology）

## 概述

方法论本体将 Devkit 的 AI 原生开发方法论形式化为四层结构：

```
O  本体层（Ontology）     — 定义 ChangeType / Phase / GateType 类及实例
G  门控层（Gate）         — 每个阶段转换点的检查规则
P  路径层（Path）         — 每种 ChangeType 的强制阶段序列
f_θ 函数层（Function）    — 门控检查的具体实现（fs_check / runtime）
```

## 文件说明

| 文件 | 用途 |
|------|------|
| `methodology.yaml` | 本体声明：ChangeType 实例、Phase 实例、强制路径、门控规则 |
| `gate-checks.yaml` | 门控实现：每个 check_key 的具体检查方式（deterministic / runtime / checklist / cross_artifact / coverage） |
| `testing-methodology.yaml` | 测试方法论：每种 ChangeType 的强制测试策略、测试步骤、覆盖率要求 |
| `complexity-tracks.yaml` | 复杂度轨道：trivial / standard / complex 的路径覆盖规则和门控放松规则 |
| `graph-schema.cypher` | Neo4j 图谱 schema：Feature 及关联节点的创建语句 |

## ChangeType 语义

| ChangeType | 说明 | 典型场景 |
|------------|------|----------|
| `new_capability` | 全新功能，从无到有 | 新增一个 Skill、新增一个 API 端点 |
| `behavior_change` | 修改已有功能的行为 | 修改提醒逻辑、调整 Agent 响应格式 |
| `bug_fix` | 修复已有功能的缺陷 | 修复时区 bug、修复 JSON 解析错误 |
| `refactoring` | 不改变外部行为的内部重构 | 提取函数、重命名变量、优化性能 |
| `doc_revision` | 文档修改 | 更新 README、补充注释 |
| `eval_asset` | 评测资产 | 新增 eval 用例、rubric 定义 |

## Phase 语义

| Phase | 说明 |
|-------|------|
| `classify` | 分类：确定 ChangeType，创建 Feature |
| `requirements` | 需求：写验收场景、明确目标 |
| `design` | 设计：写设计决策、确定方案 |
| `decomposition` | 分解：complex 功能专用，在 design 后分解为 stories |
| `implementation` | 实现：写代码 |
| `verification` | 验证：运行测试、端到端确认 |
| `asset_capture` | 资产沉淀：写回归用例、更新 MEMORY.md |
| `finalize` | 收尾：更新 STATUS.md、关闭 Feature |

## GateType 语义

| GateType | 说明 |
|----------|------|
| `hard_block` | 强制阻塞，必须满足才能进入下一阶段 |
| `soft_warn` | 软警告，可以继续但会记录警告 |
| `skip_with_reason` | 允许跳过，但必须提供跳过理由 |
| `halt_condition` | 触发 halt：记录阻塞原因，需显式 resolve 才能继续 |

## Complexity 语义

| Complexity | 说明 | 路径影响 |
|------------|------|----------|
| `trivial` | ≤3 个文件改动，无跨模块依赖 | 跳过 design 阶段 |
| `standard` | 默认复杂度 | 走完整 mandatory_path |
| `complex` | 多 story 功能 | design 后注入 decomposition 阶段，需完成 stories.json |

## 测试方法论（testing-methodology.yaml）

每种 ChangeType 定义了强制的测试策略，包括：
- `required_approaches`：必须采用的测试方法
- `ordered_steps`：测试步骤（部分步骤是 hard_block）
- `coverage_mandate`：最低覆盖率要求
- `change_point_requirements`：change-points.json 的必填字段

详见 `testing-methodology.yaml`。

## Gate Check 类型

| 类型 | 说明 |
|------|------|
| `deterministic` | 文件系统扫描：检查指定 glob 路径是否存在 |
| `runtime` | 运行命令：检查 exit_code |
| `checklist` | DoD 清单：检查 JSON 文件中所有 required 分类的条目均 completed=true |
| `cross_artifact` | 跨产物检查：检查 source_glob 文件中包含 target_pattern |
| `coverage` | 覆盖率检查：运行测试并解析 coverage.json，验证行覆盖率 ≥ min_coverage |

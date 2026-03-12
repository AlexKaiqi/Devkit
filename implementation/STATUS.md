# 当前状态

> 最后更新：2026-03-12

## 当前状态

仓库已重组为 `requirements/`、`design/`、`implementation/` 三层：

- `requirements/` 负责产品需求、能力需求和验收标准。
- `design/` 负责目标态架构、接口契约和设计决策。
- `implementation/` 负责源码、脚本、运行资产、测试和当前进展。

风铃被定义为自有移动端主客户端；Telegram 如果保留，默认只作为可选外部通知或轻量集成工具；两者共享同一个本地 runtime。

## 最近完成

- [2026-03-12] 工具执行沙箱 P0 落地（`design/decisions/tool-sandbox.md`）：
  - 新增 `runtime/tools/sandbox.py`：路径分区（安全区/受控区/禁区）+ 命令过滤（黑名单/警告）+ `check_permission()` 统一拦截
  - `tools/__init__.py` 的 `run_tool()` 增加沙箱前置检查
  - `exec.py`、`write_file.py` schema 增加 `confirmed` 可选参数支持阻塞式确认
  - 46 条单元测试全部通过（路径分类、命令过滤、读写权限、disabled 模式）
- [2026-03-12] 风铃主界面 markdown 渲染 + mermaid 支持：
  - AI 消息全面 markdown 渲染（marked.js 本地化，不依赖 CDN）
  - 流式阶段 500ms debounce 预览 markdown，完成后最终渲染 + 代码块复制按钮
  - Mermaid 图表按需加载（检测到 mermaid 代码块时才动态加载）
  - 暗色主题完整 markdown 样式（标题、列表、表格、代码、引用、链接等）
  - 设计决策更新：明确"对话即界面"原则，`/tasks` 等页面仅作开发调试入口
- [2026-03-12] 任务图 Web UI 重构：从 Cytoscape.js DAG 图切换为可折叠目录树视图
  - 移除 Cytoscape/dagre/cytoscape-dagre 三个 CDN 依赖
  - 纯 DOM 递归渲染树形结构，状态图标 + badge + 进度计数 + 焦点标记
  - 展开/折叠子树 + inline 详情面板（intent, next_action, result_summary, error_summary）
  - 默认展开规则：running/queued 自动展开，终态折叠，焦点及祖先强制展开
  - SSE 实时增量更新（已有节点 DOM 原地更新，新节点全量重载）
  - 视觉风格对齐风铃主界面暗色主题（CSS variables）
- [2026-03-12] 任务图（Task Graph）系统完整实现：
  - 需求层：`requirements/core/task-graph.md` 能力规格 + 2 个验收场景
  - 设计层：`design/decisions/task-graph-neo4j.md` Neo4j 选型 + `design/architecture/task-graph.md` 架构设计
  - 实现层 Phase 1：`implementation/runtime/task_graph/` 核心图引擎（models, graph_store, stack, orchestrator, tools, events），Neo4j Docker 容器配置，agent.py 集成（Context 注入 + 工具注册）
  - 实现层 Phase 2：Fengling REST API（6 个端点 + SSE 实时推送），Web UI（tasks.html/js/css）
  - 实现层 Phase 3：CLI 入口（list/tree/show/focus/cancel），启动恢复机制
  - 实现层 Phase 4：单元测试 + 集成测试，ops 脚本更新（start/stop/check），requirements.txt 更新
- [2026-03-09] 收敛渠道优先级：明确风铃是主客户端，Telegram 只作为可选外部集成 / 通知工具；同步更新 README、产品目标、架构决策、acceptance、tool choices 与 agent 上下文。
- [2026-03-09] 清理实现层测试表述：把 `implementation/tests/` 中残留的“主入口 / Web client”文案改成更中性的 channel/service 表达，避免把当前 transport 细节误写成产品层渠道定位。
- [2026-03-09] 纠正渠道定位理解：不再把风铃写成桌面主入口，而是定义为与 Telegram 并列的移动端用户渠道；同步更新 README、requirements、design、persona 指令与项目上下文文档。
- [2026-03-09] 补齐 requirements/acceptance/ 用例：`memory-recall-001`、`memory-correction-001`、`task-state-reporting-001`、`trust-boundary-002`、`cross-channel-delivery-001`；更新验收 README 索引。
- [2026-03-09] 新增 `design/architecture/session-identity.md`：定义 session_key 命名约定、V1 任务注册表格式（JSONL）、identity-map.yml 结构和跨渠道结果投递路径。
- [2026-03-09] 新增 `design/architecture/knowledge-gateway.md`：定义知识条目结构、从记忆层晋升触发条件、KnowledgeGateway 接口契约和 V1 实现约束。
- [2026-03-09] 补充 `design/architecture/runtime-core.md`：新增 Context Assembly 策略（组装顺序、token 预算分配、续作任务的上下文处理）。
- [2026-03-09] 新增 `design/architecture/policy-check.md`：定义委托边界数据格式（POLICY.md + DynamicGrant）、PolicyCheck 接口、TOOL_RISK_MAP 和审计记录约定。
- [2026-03-09] 新增 `design/evaluation/metrics-collection.md`：定义 audit.jsonl schema、北极星指标与核心体验指标的计算方式和 V1 采集路径。
- [2026-03-09] 新增 `design/evaluation/judge-rubrics.md` 中 `memory_utilization_v1` rubric。

- [2026-03-09] 新增 `design/decisions/ai-native-development-checklist.md`：把 AI 原生开发范式进一步落成默认执行清单，并接入根 README、设计索引、决策摘要、project context 与 AGENTS 指令。
- [2026-03-09] 新增 `design/decisions/ai-native-development.md`：把“文档/验收/评测先于实现、证据先于判断、失败样本资产化”的 AI 原生开发范式沉淀为项目级设计原则，并接入 README、决策索引和项目规则。
- [2026-03-09] 完成仓库三层重组：新增 `requirements/`、`design/`、`implementation/`，把需求、设计与实现从物理目录和文档语义上拆开。
- [2026-03-09] 新增 AI 原生测试组织：在 `requirements/acceptance/` 定义前置验收场景，在 `design/evaluation/` 定义评测协议和 rubric，在 `implementation/evals/` 增加 acceptance runner scaffold。
- [2026-03-09] 重写根目录导航与分层索引：`README.md`、`requirements/README.md`、`design/README.md`、`implementation/README.md`。
- [2026-03-09] 重写产品主叙事：明确多渠道共享同一 AI runtime，并围绕统一任务、记忆与知识资产组织产品。
- [2026-03-09] 将运行时代码、渠道实现、persona、数据、脚本和测试归入 `implementation/`，并保留根目录薄包装入口。
- [2026-03-09] 将架构、能力与服务文档拆分为需求层和设计层，减少“产品定义 / 架构设计 / 当前实现”混写。
- [2026-03-06] 自建 Agent Runtime：openai SDK 直连兼容 LLM 接口，内置 `exec` / `read_file` / `write_file` / `search` 四个工具，风铃与 Telegram 已统一接入。
- [2026-03-05] 事件驱动定时器架构落地：EventBus + Timer API 支撑异步提醒与主动回报。

## 进行中

- SearXNG 网络修复（容器内 HTTPS 出站仍不稳定）
- 工具沙箱 P1：Git auto-stash 兜底
- 记忆层与知识层的维护闭环

## 当前目录约定

| 目录 | 作用 |
|------|------|
| `requirements/` | 产品与能力需求 |
| `design/` | 目标态架构、接口与决策 |
| `implementation/runtime/` | 共享 runtime 核心 |
| `implementation/runtime/task_graph/` | 任务图系统（Neo4j DAG） |
| `implementation/channels/` | 风铃与 Telegram 渠道实现 |
| `implementation/services/` | 语音、搜索、Neo4j 等支撑服务 |
| `implementation/assets/persona/` | persona 与长期运行指令 |
| `implementation/data/` | 审计与结构化本地数据 |
| `implementation/ops/` | 启停、诊断、部署、辅助脚本 |
| `implementation/tests/` | 测试套件 |
| `implementation/evals/` | 验收评测运行器与报告 |

## 待确认

- 知识层的独立系统将以什么形式与 runtime 对接

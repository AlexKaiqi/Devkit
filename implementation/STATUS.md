# 当前状态

> 最后更新：2026-03-09

## 当前状态

仓库已重组为 `requirements/`、`design/`、`implementation/` 三层：

- `requirements/` 负责产品需求、能力需求和验收标准。
- `design/` 负责目标态架构、接口契约和设计决策。
- `implementation/` 负责源码、脚本、运行资产、测试和当前进展。

风铃被确立为默认主入口；Telegram 作为移动次入口和异步回报渠道；两者共享同一个本地 runtime。

## 最近完成

- [2026-03-09] 完成仓库三层重组：新增 `requirements/`、`design/`、`implementation/`，把需求、设计与实现从物理目录和文档语义上拆开。
- [2026-03-09] 重写根目录导航与分层索引：`README.md`、`requirements/README.md`、`design/README.md`、`implementation/README.md`。
- [2026-03-09] 重写产品主叙事：明确风铃是主入口、Telegram 是次入口、共享 AI runtime 是底座。
- [2026-03-09] 将运行时代码、渠道实现、persona、数据、脚本和测试归入 `implementation/`，并保留根目录薄包装入口。
- [2026-03-09] 将架构、能力与服务文档拆分为需求层和设计层，减少“产品定义 / 架构设计 / 当前实现”混写。
- [2026-03-06] 自建 Agent Runtime：openai SDK 直连兼容 LLM 接口，内置 `exec` / `read_file` / `write_file` / `search` 四个工具，风铃与 Telegram 已统一接入。
- [2026-03-05] 事件驱动定时器架构落地：EventBus + Timer API 支撑异步提醒与主动回报。

## 进行中

- SearXNG 网络修复（容器内 HTTPS 出站仍不稳定）
- 任务状态持久化与续作落地
- 委托边界的运行时强制检查
- 记忆层与知识层的维护闭环

## 当前目录约定

| 目录 | 作用 |
|------|------|
| `requirements/` | 产品与能力需求 |
| `design/` | 目标态架构、接口与决策 |
| `implementation/runtime/` | 共享 runtime 核心 |
| `implementation/channels/` | 风铃与 Telegram 渠道实现 |
| `implementation/services/` | 语音、搜索等支撑服务 |
| `implementation/assets/persona/` | persona 与长期运行指令 |
| `implementation/data/` | 审计与结构化本地数据 |
| `implementation/ops/` | 启停、诊断、部署、辅助脚本 |
| `implementation/tests/` | 测试套件 |

## 待确认

- 知识层的独立系统将以什么形式与 runtime 对接
- 任务状态是否在当前仓库内持久化，还是交由独立任务存储承载

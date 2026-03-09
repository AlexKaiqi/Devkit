# Devkit

> 仓库按 `requirements/`、`design/`、`implementation/` 三层组织：先定义要什么，再定义怎么设计，最后落到实际代码与运行资产。

## Quick Start

```bash
./setup.sh
./start.sh
```

根目录脚本是薄包装入口，实际实现位于 `implementation/ops/`。

## 先看哪里

| 目录 | 说明 |
|------|------|
| [requirements/](requirements/README.md) | 产品需求、能力需求、验收标准 |
| [design/](design/README.md) | 目标架构、接口契约、设计决策 |
| [implementation/](implementation/README.md) | 源码、运行资产、脚本、测试、评测与当前状态 |

## 推荐阅读顺序

1. [产品总览](requirements/product/overview.md)
2. [项目目标](requirements/product/goals.md)
3. [验收用例索引](requirements/acceptance/README.md)
4. [能力需求总览](requirements/capabilities/overview.md)
5. [系统设计总览](design/architecture/system-overview.md)
6. [AI 原生开发范式](design/decisions/ai-native-development.md)
7. [AI 原生开发清单](design/decisions/ai-native-development-checklist.md)
8. [评测协议](design/evaluation/eval-protocol.md)
9. [实现层导航](implementation/README.md)

## 入口

| 渠道 | 角色 | 说明 |
|------|------|------|
| 风铃 | 主入口 | 默认桌面工作台，优先承载高频交互与任务发起 |
| Telegram | 次入口 | 移动侧发起请求、接收异步结果与提醒 |

## 仓库原则

- `requirements/` 只回答用户价值、对象、流程与验收标准。
- `design/` 只回答系统边界、模块关系、接口与设计决策。
- `implementation/` 才描述代码、脚本、环境变量、端口、测试与运行现状。
- 面向 AI 实现的验收场景优先定义在 `requirements/acceptance/`，而不是事后补到实现层。

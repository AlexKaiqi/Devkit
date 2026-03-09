# Implementation

`implementation/` 收纳实际源码、运行资产、脚本、测试和当前状态。

## 边界

- 这里可以出现代码路径、端口、环境变量、脚本命令、部署方式、测试入口。
- 这里不重新定义产品需求；如果需求变了，应先改 `requirements/` 和 `design/`。

## 目录

| 目录 | 说明 |
|------|------|
| [runtime/](runtime/) | 共享 agent runtime 核心 |
| [channels/](channels/) | 风铃与 Telegram 渠道实现 |
| [services/](services/) | 语音、搜索等支撑服务 |
| [assets/](assets/) | persona 等运行时资产 |
| [data/](data/) | 审计与结构化本地数据 |
| [ops/](ops/) | 启停、诊断、部署、辅助脚本 |
| [tests/](tests/) | 测试套件 |
| [evals/](evals/) | AI 原生验收评测运行器与报告 |
| [STATUS.md](STATUS.md) | 当前实现状态与最近进展 |

## 常用入口

```bash
./setup.sh
./start.sh
./check.sh --json
./stop.sh
```

这些根目录命令会转发到 `implementation/ops/` 下的实际脚本。

## `tests/` 与 `evals/` 的区别

- `implementation/tests/`：确定性工程测试，如 unit / integration / component / e2e。
- `implementation/evals/`：面向需求层验收 case 的运行器、报告和 evidence 处理。

# 服务职责映射

本文档描述目标态服务职责映射，不跟踪当前是否已落地。

## 运行时核心

| 模块 | 主要职责 | 属于哪层 |
|------|----------|----------|
| Runtime Core | 任务编排、上下文组装、记忆/知识接入、工具协调 | runtime |
| Tool Protocol | 为 runtime 暴露统一工具面 | runtime |
| Event System | 承载定时器、续作、主动通知与外部回调 | runtime |
| Model Adapter Layer | 隔离模型提供商差异 | runtime |

## 产品入口

| 模块 | 主要职责 | 说明 |
|------|----------|------|
| 风铃 | 主入口、流式交互、附件与语音体验 | 默认优先定义体验 |
| Telegram | 次入口、异步回报、移动续作 | 共享同一 runtime |

## 支撑服务

| 模块 | 主要职责 |
|------|----------|
| Speech Service | 语音识别与语音合成接入 |
| Search Service | 通用检索能力 |
| CLI / MCP / HTTP Connectors | 承接开发、科研、人际、家居等外部能力 |
| Knowledge Backend | 承载结构化知识资产 |

## 运行资产

| 资产 | 作用 |
|------|------|
| Persona Assets | 承载分身人格、原则和长期操作指令 |
| Local Data | 承载结构化数据和审计 |
| Ops Scripts | 启停、诊断、部署和自动化辅助 |
| Tests | 验证 runtime、渠道与支撑服务 |

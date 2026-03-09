# 决策摘要

这个文件保留一份简要摘要，方便快速回看；正式的决策按主题拆分在同目录下。

| 主题 | 摘要 | 详细文档 |
|------|------|----------|
| 渠道与入口 | 风铃是主客户端，Telegram 是可选外部集成，共享同一 runtime | [channel-entry.md](channel-entry.md) |
| 交互模型 | 条件语音、文本/附件分区、长任务先反馈后异步推进 | [interaction-model.md](interaction-model.md) |
| AI 原生开发 | 文档、验收、评测先于实现，失败样本要沉淀成长期资产 | [ai-native-development.md](ai-native-development.md) / [ai-native-development-checklist.md](ai-native-development-checklist.md) |
| 工具原则 | 开源优先、CLI/HTTP/MCP 优先，不把测试工具误写成主路径依赖 | [tooling-principles.md](tooling-principles.md) |
| 记忆与知识 | 记忆层与知识层分离定义，知识层实现允许解耦 | [memory-knowledge.md](memory-knowledge.md) |
| runtime 与适配层 | 产品资产归 runtime，自建薄模型适配层 | [runtime-and-adapter.md](runtime-and-adapter.md) |
| 事件与通知 | 定时器、提醒、续作统一走事件系统 | [eventing-and-notification.md](eventing-and-notification.md) |
